# Approach log · Brief <LETTER> · Group <N>

One row per part of the work. At least two approaches in every row. Written when the choice is made, not afterwards; the commit timestamp is the proof. An approach you tried for twenty minutes and abandoned is the best kind of row. Keep the dead notebook cell and link to it.

The panel reads this file before it reads your notebooks. A panellist will cover the "chosen" column and ask you to choose again, aloud.

| # | Part of the work | Approaches considered (two at least) | Chosen | Why this, and not the others | What would have changed the choice | What happened when we tried it | Owner | Date |
|---|---|---|---|---|---|---|---|---|
| 0 | *Example: matching invoice ids to payment references* | *(a) Strip the prefix and match on digits. (b) Match on amount and date within two days. (c) Both, and keep the rows where they disagree.* | *(c)* | *(a) alone matched 91 percent and silently paired two invoices with one payment. (b) alone could not separate same-day same-amount visits. Together they flag what each misses.* | *A shared id in both feeds would have made (a) enough.* | *96 percent matched. The 4 percent became finance's list.* | *example* | *example* |
| 1 | Which table to count tests from | | | | | | | |
| 2 | How to define the period (first half, both years) | | | | | | | |
| 3 | Profiling: what to check in each table | | | | | | | |
| 4 | Duplicates: the identity rule | | | | | | | |
| 5 | Missing values: drop, default, or keep and flag | | | | | | | |
| 6 | Each join: type, key, validation | | | | | | | |
| 7 | The method (tree / ladder / bridge / shuffle / comparison) | | | | | | | |
| 8 | The segmentation (city, channel, type) | | | | | | | |
| 9 | The chart that carries the claim | | | | | | | |
| 10 | The one sentence | | | | | | | |

## Parts we never had to choose about

<List any part where only one approach was possible, and say why. The panel will ask whether that was true.>
