"""Snake-draft simulation and replacement level."""
import numpy as np
import pandas as pd

POSITIONS = ("F", "D", "G")


def replacement_levels(proj: pd.DataFrame, teams: int, slots: dict, col: str = "proj_FP") -> dict:
    """Projection of the first player at each position who would go undrafted."""
    out = {}
    for pos in POSITIONS:
        vals = proj.loc[proj["pos"] == pos, col].sort_values(ascending=False).to_numpy()
        n = int(round(teams * slots[pos]))
        out[pos] = float(vals[n]) if len(vals) > n else 0.0
    return out


def snake_order(teams: int, rounds: int) -> list[int]:
    order = []
    for r in range(rounds):
        seq = range(teams) if r % 2 == 0 else range(teams - 1, -1, -1)
        order.extend(seq)
    return order


def best_ball(values: pd.Series, pos: pd.Series, counted: dict) -> float:
    """Sum of the best `counted[p]` values at each position."""
    return float(sum(values[pos == p].nlargest(n).sum() for p, n in counted.items()))


def simulate(mine: pd.Series, opp: pd.Series, pos: pd.Series, actual: pd.Series,
             teams: int, slots: dict, my_pick: int, my_vorp: bool = True, opp_vorp: bool = False,
             counted: dict | None = None, my_draws: pd.DataFrame | None = None, n_cand: int = 25,
             my_repl: dict | None = None, dynamic: bool = False, my_bonus: pd.Series | None = None,
             goalie_rule: dict | None = None, my_late: pd.Series | None = None, late_round: int = 99,
             opp_noise: float = 0.0, scarcity: dict | None = None, seed: int = 0) -> dict:
    """Draft `slots` players per position; score each team by best-ball `counted`.

    mine / opp: projection per playerId used by my team / by every opponent.
    Each drafter takes the best available at a position still open, by raw
    projection or by projection minus replacement level (VORP).
    Options for my team:
      dynamic     replacement level recomputed before each of my picks from the
                  players still available (what the board does)
      my_bonus    points added to my sort value (favorite-team bonus)
      goalie_rule {"first_round": r} no goalie before round r;
                  {"second_last": k} second goalie only in the last k rounds
      my_late     alternative projection used from round late_round+1 on
                  (for example an upside percentile)
      my_draws    best-ball-aware picks from simulated seasons (tested, rejected)
      scarcity    {"margin": m, "sims": n, "noise": x}: among positions whose best value
                  is within m points of the overall best, take the one expected to
                  lose the most by my next pick. The loss is simulated with opponents
                  drafting by my projections times exp(N(0, x)), the backtest's
                  stand-in for the board's public-projection opponents.
    opp_noise: opponents' projections are multiplied by exp(N(0, opp_noise)).
    Returns my actual total, the opponents' mean, my finishing rank and the
    same split by position.
    """
    ids = mine.index.union(opp.index)
    pos = pos.reindex(ids)
    rounds = sum(slots.values())
    order = snake_order(teams, rounds)
    rng = np.random.default_rng(seed)

    def score_vec(proj, vorp, repl_slots=None):
        proj = proj.reindex(ids).fillna(-1e9)
        if not vorp:
            return proj
        rl = replacement_levels(pd.DataFrame({"pos": pos, "proj_FP": proj}), teams, repl_slots or slots)
        return proj - pos.map(rl)

    opp_proj = opp.reindex(ids).fillna(-1e9)
    if opp_noise:
        opp_proj = opp_proj * np.exp(rng.normal(0, opp_noise, len(opp_proj)))
    s_opp = score_vec(opp_proj, opp_vorp).to_numpy()
    s_mine = score_vec(mine, my_vorp, my_repl).to_numpy()
    raw_mine = mine.reindex(ids).fillna(-1e9).to_numpy()
    raw_late = my_late.reindex(ids).fillna(-1e9).to_numpy() if my_late is not None else None
    bonus = my_bonus.reindex(ids).fillna(0.0).to_numpy() if my_bonus is not None else 0.0
    pos_arr = pos.to_numpy()
    avail = np.ones(len(ids), dtype=bool)
    need = [dict(slots) for _ in range(teams)]
    rosters = [[] for _ in range(teams)]
    me = my_pick - 1
    counted = counted or slots
    D = my_draws.reindex(ids).fillna(0.0).to_numpy() if my_draws is not None else None
    taken = {p: 0 for p in slots}
    repl_slots = my_repl or slots
    if scarcity:
        srng = np.random.default_rng(seed + 1_000_003)
        rl = replacement_levels(pd.DataFrame({"pos": pos, "proj_FP": mine.reindex(ids).fillna(-1e9)}), teams, slots)
        mine_repl = pos.map(rl).to_numpy()
    for k, t in enumerate(order):
        rnd = k // teams + 1
        ok = avail & np.isin(pos_arr, [p for p, n in need[t].items() if n > 0])
        if t == me:
            if goalie_rule:
                g_have = slots["G"] - need[t]["G"]
                left = rounds - rnd + 1
                sk_need = sum(n for p, n in need[t].items() if p != "G")
                block = (g_have == 0 and rnd < goalie_rule.get("first_round", 0)) or \
                        (g_have == 1 and left > goalie_rule.get("second_last", 99))
                if block and sk_need > 0:
                    ok = ok & (pos_arr != "G")
            if D is not None:
                i = _best_ball_pick(D, raw_mine, pos_arr, ok, rosters[me], ids, slots, counted, taken, teams, n_cand)
            else:
                raw = raw_late if (raw_late is not None and rnd > late_round) else raw_mine
                if my_vorp and (dynamic or raw is raw_late):
                    sv = raw.copy()
                    for p in slots:
                        m = avail & (pos_arr == p)
                        vals = np.sort(raw[m])[::-1]
                        n_open = max(int(round(teams * repl_slots[p])) - taken[p], 0)
                        sv[pos_arr == p] -= vals[min(n_open, len(vals) - 1)] if len(vals) else 0.0
                else:
                    sv = s_mine
                score = np.where(ok, sv + bonus, -np.inf)
                i = int(np.argmax(score))
                nxt = next((j for j in range(k + 1, len(order)) if order[j] == me), None)
                if scarcity and nxt is not None:
                    i = _scarcity_pick(score, i, pos_arr, avail, need, order[k + 1:nxt], raw_mine,
                                       mine_repl, scarcity, srng)
        else:
            i = int(np.argmax(np.where(ok, s_opp, -np.inf)))
        taken[pos_arr[i]] += 1
        avail[i] = False
        need[t][pos_arr[i]] -= 1
        rosters[t].append(ids[i])
    act = actual.reindex(ids).fillna(0.0)
    by_pos = np.array([[best_ball(act.loc[r], pos.loc[r], {p: counted[p]}) for p in counted] for r in rosters])
    totals = by_pos.sum(axis=1)
    my_total = totals[me]
    others = np.delete(totals, me)
    out = {"my_total": my_total, "opp_mean": others.mean(), "margin": my_total - others.mean(),
           "rank": int((totals > my_total).sum() + 1)}
    for j, p in enumerate(counted):
        out[f"margin_{p}"] = by_pos[me, j] - np.delete(by_pos[:, j], me).mean()
    return out


def _scarcity_pick(score, i_best, pos_arr, avail, need, between, raw, repl, cfg, rng):
    """Pick at the position that loses the most by waiting, among positions close in value."""
    open_pos = [p for p in POSITIONS if np.isfinite(score[pos_arr == p]).any()]
    best_now = {p: score[pos_arr == p].max() for p in open_pos}
    top = max(best_now.values())
    close = [p for p in open_pos if best_now[p] >= top - cfg["margin"]]
    if len(close) < 2 or not len(between):
        return i_best
    nxt = {p: [] for p in close}
    for _ in range(cfg.get("sims", 30)):
        av = avail.copy()
        nd = [dict(x) for x in need]
        proxy = raw * np.exp(rng.normal(0, cfg.get("noise", 0.15), len(raw))) - repl
        for t in between:
            m = av & np.isin(pos_arr, [p for p, n in nd[t].items() if n > 0])
            j = int(np.argmax(np.where(m, proxy, -np.inf)))
            av[j] = False
            nd[t][pos_arr[j]] -= 1
        for p in close:
            left = np.where(av & (pos_arr == p), score, -np.inf)
            nxt[p].append(left.max() if np.isfinite(left).any() else best_now[p] - 1e3)
    drop = {p: best_now[p] - np.mean(nxt[p]) for p in close}
    p_take = max(close, key=drop.get)
    return int(np.argmax(np.where(pos_arr == p_take, score, -np.inf)))


def _topk_mean(M: np.ndarray, k: int) -> float:
    """Mean over sims of the sum of the k largest rows (M: players x sims)."""
    if M.shape[0] <= k:
        return float(M.sum(axis=0).mean())
    return float(np.sort(M, axis=0)[-k:].sum(axis=0).mean())


def _best_ball_pick(D, raw, pos_arr, ok, my_ids, ids, slots, counted, taken, teams, n_cand):
    idx_of = {pid: j for j, pid in enumerate(ids)}
    best_i, best_v = None, -np.inf
    for p in {pos_arr[j] for j in np.flatnonzero(ok)}:
        cand = np.flatnonzero(ok & (pos_arr == p))
        cand = cand[np.argsort(-raw[cand])]
        open_slots = max(teams * slots[p] - taken[p], 1)
        repl = cand[min(open_slots, len(cand) - 1)]
        R = D[[idx_of[x] for x in my_ids if pos_arr[idx_of[x]] == p]] if my_ids else np.zeros((0, D.shape[1]))
        base = _topk_mean(np.vstack([R, D[repl]]), counted[p])
        for j in cand[:n_cand]:
            v = _topk_mean(np.vstack([R, D[j]]), counted[p]) - base
            if v > best_v:
                best_i, best_v = int(j), v
    return best_i
