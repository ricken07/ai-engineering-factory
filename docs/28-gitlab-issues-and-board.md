# 28 — GitLab Issues et Issue Board

## Cible

GitLab Issues peut porter les Tasks durables tandis qu'un Issue Board fournit
une vue de pilotage. Le Core ne connaît ni GitLab ni les noms de ses outils : il
demande exclusivement la capability `task-provider`.

```text
Task locale ou référence GitLab
  → task-provider
  → Integration Resolver
  → mapping d'opération vérifié
  → GitLab MCP
  → GitLab Issue
  → labels de workflow
  → Issue Board
```

## Périmètre du MCP GitLab natif

Le catalogue central mappe uniquement les opérations actuellement vérifiées :

| Factory | Outil GitLab MCP |
| --- | --- |
| `get-task` | `get_issue` |
| `search-task` | `search` |
| `create-task` | `create_issue` |
| `comment-task` | `create_workitem_note` |
| `link-task` | `link_work_items` |
| `link-change` | `link_work_items` |

`update-task` n'est pas annoncé par le provider natif. Une tentative de le
résoudre retourne `CAPABILITY_UNSUPPORTED`. Il n'existe aucun fallback REST
silencieux.

Pour supporter ultérieurement `update-task`, l'organisation doit fournir un
provider/gateway MCP gouverné qui implémente explicitement l'opération. Les
Skills Core restent inchangés.

## Configuration projet

Le projet active seulement les capabilities et son modèle de Task :

```yaml
integrations:
  source-control: {provider: gitlab}
  continuous-integration: {provider: gitlab}
  task-provider: {provider: gitlab}

taskTracking:
  mode: external
  namespace: Gad-Digital-IT/products/emi-ai
  referenceFormat: container-iid
  workflowStates:
    - workflow::backlog
    - workflow::ready
    - workflow::doing
    - workflow::review
    - workflow::done
  defaultLabels:
    - workflow::backlog
```

`namespace`, les labels et le format de référence sont du contexte projet. URL,
transport et authentification MCP restent dans le catalogue organisationnel et
les adapters.

## Références polyrepo

Une référence `#42` est ambiguë dans un workspace polyrepo. Utiliser :

```text
Gad-Digital-IT/products/emi-ai/app#42
```

ou l'URL complète :

```text
https://gitlab.com/Gad-Digital-IT/products/emi-ai/app/-/issues/42
```

Le Runtime conserve la référence complète comme identité canonique.

## Création et board

Une `ExternalTaskProposal` peut sélectionner le projet GitLab cible et les
labels :

```yaml
kind: ExternalTaskProposal
sourceTask: local-...
title: Corriger le contrat Homework
description: ...
acceptanceCriteria: [...]
repositories: [emi-ai-api, emi-ai-app]
risk: high
target:
  container: app
labels:
  - type::bug
  - component::backend
```

Le Runtime ajoute le namespace et les `defaultLabels`. La création reste
interdite avant la recherche de doublons et le human gate. Une Issue créée avec
`workflow::backlog` apparaît dans la liste correspondante du board.

## Authentification

Le MCP officiel GitLab utilise OAuth. Claude Code peut utiliser directement le
transport HTTP natif. Avec certaines versions de Codex CLI, `codex mcp login
gitlab` échoue avec une erreur `Authorization server issuer mismatch`.

Dans ce cas, utiliser le pont OAuth STDIO `mcp-remote` :

```toml
[mcp_servers.gitlab]
command = "npx"
args = ["-y", "mcp-remote@0.1.26", "https://gitlab.com/api/v4/mcp", "--static-oauth-client-metadata", '{"scope":"mcp"}']
```

La version est volontairement figée afin d'éviter une mise à jour implicite
d'une dépendance tierce sur le chemin d'authentification. Le navigateur
s'ouvre au démarrage de Codex ; `codex mcp login gitlab` n'est pas nécessaire
avec cette configuration.

Il ne doit exister qu'une seule définition `mcp_servers.gitlab`. Ne mélangez
jamais `url`/`bearer_token_env_var` (HTTP Bearer) et `command`/`args` (STDIO)
dans le même bloc. Une configuration utilisateur dans `~/.codex/config.toml`
et une configuration projet dans `.codex/config.toml` portant le même nom
peuvent également être fusionnées par Codex.

Après modification, vérifier depuis la racine du projet :

```bash
codex mcp list
codex
```

Le token GitLab n'est pas écrit dans le projet. Avec OAuth `mcp-remote`, il est
conservé dans le cache d'authentification local du pont MCP.

## Validation

```bash
aief integrations lock "$PROJECT_ROOT" --factory "$AIEF_HOME"
aief integrations doctor "$PROJECT_ROOT" --factory "$AIEF_HOME"
aief validate "$PROJECT_ROOT" --factory "$AIEF_HOME"
```

Avant la première mutation, vérifier en lecture seule la version MCP, une Issue
existante, une recherche de work items et les labels du namespace.
