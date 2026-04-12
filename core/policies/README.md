# Core Policies

Policies define permissions, restrictions, required gates and resolution behavior. They do not define delivery phase order.

Policy layers may add restrictions. The effective decision uses the strongest risk, lowest autonomy ceiling, union of required gates and union of denied actions.

Files in this directory are provider-, stack- and agent-agnostic.
