# Economics and quantitative-data research

Apply this guide to official statistics, prices, rates, currencies, money,
ratios, surveys, forecasts, market estimates, and calculated comparisons.

## Define the measure before comparing it

Record the producer, dataset and series, geography, covered population,
reference period, release vintage, frequency, unit, scale, currency, price
basis, seasonal-adjustment status, and whether the value is a level, index,
flow, stock, rate, share, or change.

Explicitly distinguish:

- nominal from real and the stated base year or deflator;
- seasonally adjusted from unadjusted;
- total from per-capita and aggregate from component series;
- current-price from constant-price values;
- percentage change from percentage-point change;
- preliminary, revised, benchmarked, forecast, and final values;
- calendar, fiscal, rolling, and year-over-year periods.

## Source order

1. The producing statistical agency, central bank, regulator, exchange, company
   filing, or dataset owner.
2. That producer's metadata, methodology, release calendar, revision policy,
   and uncertainty or sampling documentation.
3. A recognized international harmonizer only after confirming whether it
   transforms, rebases, seasonally adjusts, converts, or revises source data.
4. Independent analysis for interpretation, never as a silent replacement for
   the underlying series.

## Numeric verification

- Copy values from the table or machine-readable series that actually defines
  the measure, not from a chart, search snippet, or article paraphrase.
- Preserve source precision. Do not add meaningful digits by calculation.
- For every derived figure, retain the source values, formula, direction,
  denominator, rounding rule, and resulting unit. Recalculate independently.
- Use the exchange rate for the stated date or period and identify its source.
- Compare like definitions and vintages. If harmonization would require an
  assumption, report the values separately instead of producing a false ranking.
- Check whether newer releases revised earlier observations. State the vintage
  when a historical value can change over time.
- Carry confidence intervals, standard errors, sampling limitations, and
  methodology breaks when they could change the conclusion.

## Cross-domain composition

Also apply [news.md](news.md) when reporting a new release, policy decision,
company announcement, market-moving event, or contested public interpretation.
Apply [software-documentation.md](software-documentation.md) when the result
depends on a data API, package, query parameter, or machine-readable schema.

## Method sources

- [IMF Data Quality Assessment Framework](https://dsbb.imf.org/content/pdfs/dqrs_Genframework.pdf)
- [U.S. Bureau of Labor Statistics Handbook of Methods](https://www.bls.gov/opub/hom/about.htm)
- [BLS seasonal-adjustment methodology](https://www.bls.gov/cpi/seasonal-adjustment/methodology.htm)
