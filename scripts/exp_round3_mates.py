"""Round 3: teammates. Team context (backtestable) and actual linemates (leaky upper bound)."""
from nhlpool import tune
from nhlpool.experiments import Runner

r = Runner(); P = dict(r.P)
print("reference rate loss:", round(r.ctx.losses(P)["rate"], 5))
p, df = tune.grid(r.ctx, P, {"team_ctx": [0.0, 0.1, 0.2, 0.3, 0.5, 0.75]}, "rate")
print("team context (known preseason):"); print(df[["team_ctx", "rate"]].to_string(index=False))
p2, df2 = tune.grid(r.ctx, P, {"line_ctx": [0.0, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0]}, "rate")
print("actual linemates (UPPER BOUND, uses in-season info):"); print(df2[["line_ctx", "rate"]].to_string(index=False))
