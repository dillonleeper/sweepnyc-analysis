# Equity analysis: who actually gets a car-free Halloween?

A data science add-on to the [Trick-or-Streets Router](../index.html): does NYC DOT hand out
its car-free Halloween streets in proportion to where the city's kids actually live, or do
some boroughs get shortchanged?

## Method

1. **Event data** — the same 2026 Trick-or-Streets dataset the router app uses, pulled directly
   from NYC DOT's own ArcGIS FeatureServer (`TrickOrStreet_Point_View`). 151 event-nights,
   collapsed to **145 unique street closures** across 5 boroughs (a handful of locations repeat
   across multiple nights).
2. **Population & land area** — NY State Dept. of Health, [*Population, Land Area, and
   Population Density by County, New York State – 2020*](https://healthweb-back.health.ny.gov/statistics/vital_statistics/2020/table02.htm)
   (2020 Decennial Census counts; each NYC borough = one county).
3. **Share of population under 18** — U.S. Census Bureau QuickFacts, American Community Survey
   2020–2024 5-year estimates, per county:
   [Bronx](https://www.census.gov/quickfacts/bronxcountynewyork) ·
   [Kings/Brooklyn](https://www.census.gov/quickfacts/fact/csv/kingscountynewyork/AGE295225) ·
   [New York/Manhattan](https://www.census.gov/quickfacts/newyorkcountynewyork) ·
   [Queens](https://www.census.gov/quickfacts/queenscountynewyork) ·
   [Richmond/Staten Island](https://www.census.gov/quickfacts/richmondcountynewyork).
4. Joined on borough name and converted to three access metrics: closures per 100,000 residents,
   closures per 10,000 *children*, and closures per 100 square miles.

**Caveat worth stating plainly:** the population counts are a fixed 2020 Census snapshot while
the under-18 share is a rolling 2020–2024 ACS estimate — a minor vintage mismatch, noted rather
than hidden. With only 5 boroughs, this is a descriptive finding, not a statistically powered
one — but the gap is large enough that it doesn't need a p-value to be worth asking DOT about.

## Results

| Borough | Closures | Population (2020) | Est. children | % under 18 | Per 100k residents | **Per 10k children** | Per 100 sq mi |
|---|---:|---:|---:|---:|---:|---:|---:|
| Manhattan | 36 | 1,611,989 | 207,947 | 12.9% | 2.23 | **1.73** | 158.87 |
| Brooklyn | 60 | 2,538,934 | 525,559 | 20.7% | 2.36 | **1.14** | 86.48 |
| Bronx | 23 | 1,401,142 | 329,268 | 23.5% | 1.64 | **0.70** | 54.54 |
| Queens | 23 | 2,225,821 | 405,099 | 18.2% | 1.03 | **0.57** | 21.16 |
| Staten Island | 3 | 475,327 | 96,967 | 20.4% | 0.63 | **0.31** | 5.22 |

![Chart: fewest closures per kid by borough, and the inverse relationship between child
population share and closures per child](equity_chart.png)

## Finding

Raw closure counts mostly just track overall population (r = 0.83 between borough population and
closure count — bigger borough, more events, no surprise there). But **weighted by the actual
number of kids who'd use them, the pattern flips**: Manhattan — the borough with the *smallest*
share of children (12.9%) — gets the *most* car-free Halloween access per child (1.73 per 10k),
while the Bronx and Staten Island, which have the city's highest shares of children (23.5% and
20.4%), get the least (0.70 and 0.31 per 10k). The correlation between a borough's child
population share and its closures-per-child rate is **r = -0.69** — a sizeable inverse
relationship for just 5 data points.

Staten Island is the extreme case either way: only 3 closures total, which comes out to roughly
a third of Manhattan's per-child rate and less than a fifth of Queens' per-square-mile rate.

## Files

- `equity_analysis.py` — the join + metrics, re-runnable (`python3 equity_analysis.py`)
- `equity_results.json` — output table
- `equity_chart.png` — the two charts above
