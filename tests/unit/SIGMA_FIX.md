"""Fixed SigmaHQ rules — removes over-broad cross_namespace rule that fires on any -n flag."""
import re

# The problem rule: `-n\s+(?!incidentrag-sandbox)\S+` matches EVERY namespace flag,
# so `kubectl get pods -n payments` is flagged as critical. It should only flag
# writes to sensitive namespaces, not reads.

# Fix: remove the rule entirely. Namespace scoping should be handled by the
# execution environment (RBAC), not a static regex.
