# 2026-27 pool: team ratings after the draft

12 teams, 16 rounds, snake. Each score is the best-ball total: best 6 F + best 4 D + best 1 G, in season
points under league scoring. The number in brackets is the team's rank under that source. Sorted by the
consensus, the plain average of the five point sources.

- **Model**: our projections. M. Bélanger drafted with it, so it favors that team by construction.
- **ESPN**: ESPN's projections as published, scored with league rules.
- **NHL.com**: NHL.com point projections, split into goals and assists with our goal share. Skaters only.
- **CBS**: CBS Sports projections. CBS gives every skater about 81 games, so its per-game rates are used
  with our games played.
- **HockeyBangers**: free player pages (goals and assists per 82 games), with our games played. Skaters only.
- **ESPN draft rank**, **FantasyPros**: ranking-only sources, put on our points scale by position rank. ESPN's rank
  is built for ESPN's default scoring (hits and blocks count); FantasyPros is a roto consensus of 2 experts.
  Neither is built for this league, so they are shown but not used in the odds.
- Missing game-winning goals and hat tricks come from each source's goals, as in our model. A player a
  source does not cover gets the average of the sources that do.

Drafted players each source covers (of 192): Model 192, ESPN 180, NHL.com 161, CBS 179, HockeyBangers 168.

| Manager | Slot | Model | ESPN | NHL.com | CBS | HockeyBangers | Consensus | ESPN draft rank | FantasyPros |
|---|---|---|---|---|---|---|---|---|---|
| M. Bélanger | 2 | 844 (1) | 840 (4) | 921 (4) | 892 (2) | 837 (1) | 867 (1) | 751 (6) | 802 (1) |
| F. Fusey | 7 | 813 (2) | 877 (1) | 937 (2) | 889 (3) | 817 (2) | 865 (2) | 786 (5) | 796 (3) |
| J. Gobeil | 6 | 787 (3) | 851 (2) | 943 (1) | 897 (1) | 812 (3) | 858 (3) | 725 (9) | 772 (5) |
| A. Cordeau | 10 | 786 (4) | 846 (3) | 905 (6) | 847 (6) | 808 (4) | 835 (4) | 735 (8) | 785 (4) |
| D. Archambault | 1 | 760 (5) | 823 (6) | 936 (3) | 858 (4) | 780 (5) | 823 (5) | 667 (11) | 796 (2) |
| P. Fiset | 4 | 743 (9) | 840 (5) | 920 (5) | 840 (7) | 740 (9) | 815 (6) | 789 (4) | 760 (6) |
| P. Allard | 3 | 756 (6) | 812 (7) | 892 (8) | 848 (5) | 762 (7) | 811 (7) | 791 (3) | 760 (7) |
| S. Marcoux | 11 | 753 (8) | 806 (8) | 885 (9) | 824 (8) | 756 (8) | 803 (8) | 718 (10) | 739 (9) |
| B. Belanger | 9 | 755 (7) | 736 (12) | 896 (7) | 806 (9) | 763 (6) | 790 (9) | 657 (12) | 748 (8) |
| L. Girard | 5 | 719 (10) | 768 (9) | 833 (10) | 772 (10) | 734 (10) | 761 (10) | 738 (7) | 697 (11) |
| M. Gosselin | 8 | 694 (11) | 754 (10) | 819 (11) | 733 (11) | 696 (11) | 736 (11) | 803 (2) | 710 (10) |
| D. Giroux | 12 | 656 (12) | 738 (11) | 782 (12) | 719 (12) | 649 (12) | 705 (12) | 815 (1) | 688 (12) |

## Finishing odds, all sources combined

20,000 simulated seasons. In each one, random weights over the five point sources decide where the truth
sits, since we do not know which source is best this year. On top of that come player-level surprises
(injuries, slumps, breakouts, goalies losing the job) drawn from how wrong projections were in past seasons,
which gave 80% ranges that held 80% of the time. Rosters are fixed (draft and hold) and only the best
6 F, 4 D and 1 G count. The last column is the model alone, for comparison.

| Manager | Expected total | Avg finish | Win % | Top 3 % | Bottom 3 % | Last % | Model-only win % |
|---|---|---|---|---|---|---|---|
| M. Bélanger | 934.0 | 3.8 | 25.4 | 56.2 | 4.1 | 0.6 | 45.6 |
| F. Fusey | 917.0 | 4.4 | 15.5 | 45.6 | 5.1 | 0.7 | 14.0 |
| J. Gobeil | 907.0 | 4.8 | 14.4 | 40.7 | 8.6 | 1.4 | 7.4 |
| D. Archambault | 902.0 | 5.0 | 13.0 | 37.0 | 9.7 | 1.6 | 8.4 |
| A. Cordeau | 900.0 | 5.1 | 12.8 | 37.0 | 10.6 | 1.7 | 7.5 |
| P. Fiset | 875.0 | 6.2 | 6.1 | 22.9 | 16.4 | 2.8 | 2.5 |
| P. Allard | 869.0 | 6.4 | 4.9 | 21.1 | 18.8 | 3.9 | 4.0 |
| B. Belanger | 853.0 | 7.1 | 2.8 | 13.6 | 24.9 | 5.0 | 5.1 |
| S. Marcoux | 849.0 | 7.3 | 3.2 | 13.9 | 28.2 | 6.6 | 3.5 |
| L. Girard | 830.0 | 8.1 | 1.2 | 7.5 | 36.9 | 9.0 | 1.3 |
| M. Gosselin | 802.0 | 9.2 | 0.6 | 3.9 | 54.6 | 18.9 | 0.7 |
| D. Giroux | 755.0 | 10.7 | 0.1 | 0.6 | 81.9 | 47.8 | 0.0 |

Not included: players on the same NHL team rising or falling together, and every source being wrong in
the same direction. Both would widen the odds a little, not change the order. Rebuild with
`uv run python scripts/rate_teams.py`.
