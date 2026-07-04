## 2024-07-04 - Django Subquery Aggregation Optimization
**Learning:** Using `prefetch_related` to load objects and sum/count them in Python memory causes massive serialization overhead for simple counts. Using `.annotate()` with `Subquery` and `OuterRef` alongside database aggregation functions (`Sum`, `Count`) computes this directly at the DB level, greatly minimizing Python memory consumption and deserialization times.
**Action:** Always prefer computing basic aggregations (sums, counts) with `Subquery` inside `annotate()` instead of pulling full object models into Python context.
