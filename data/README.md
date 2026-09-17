# Local data directory

Do not commit raw NYC Open Data extracts or generated analytical datasets here.

Recommended local layout:

```text
data/
├── raw/
├── interim/
└── processed/
```

The extraction code should record source dataset IDs, query/filter parameters, and extraction timestamps so datasets can be reproduced.
