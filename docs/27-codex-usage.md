# 27 — Utiliser la Factory avec Codex

Ce guide décrit le parcours Codex complet, depuis l'installation de l'adapter
jusqu'au diagnostic d'une exécution. Le guide général d'installation reste
[`22-project-installation-guide.md`](22-project-installation-guide.md).

## 1. Syntaxe à retenir

Codex et Claude Code n'utilisent pas la même syntaxe native :

```text
Codex       $implement Feature 1.2 — Distinguer répondu/évalué/correct
Claude      /implement Feature 1.2 — Distinguer répondu/évalué/correct
```

Dans Codex, `/implement` est invalide. Le préfixe `/` est réservé aux commandes
intégrées proposées par l'interface Codex. Les Skills Factory s'invoquent avec
`$`, ou simplement en langage naturel :

```text
$fix Corrige le mapping du statut FAILED.

Implémente Feature 1.2 en respectant le workflow Factory.
```

Les deux formulations doivent produire la même chaîne
`Task → Workflow → Execution`. La commande native précise seulement l'intention.

## 2. Préparer le poste

Définir le chemin absolu de la Factory dans le profil du shell :

```bash
export GAD_AI_FACTORY_HOME="/absolute/path/to/ai-engineering-factory"
```

Vérifier ensuite le CLI et la Factory :

```bash
printenv GAD_AI_FACTORY_HOME
aief --help
test -f "$GAD_AI_FACTORY_HOME/factory.yaml"
```

La configuration du shell sert à l'onboarding et à la résolution initiale.
Pendant un workflow, l'adapter doit résoudre cette valeur une fois puis fournir
aux commandes `aief` un chemin absolu littéral.

## 3. Installer l'adapter Codex

Prévisualiser d'abord l'installation :

```bash
aief setup-adapter codex --factory "$GAD_AI_FACTORY_HOME"
```

Puis créer les liens gérés par la Factory :

```bash
aief setup-adapter codex \
  --factory "$GAD_AI_FACTORY_HOME" \
  --execute
```

Les Skills sont exposés dans `~/.agents/skills/`. Vérifier au minimum :

```bash
test -f "$HOME/.agents/skills/implement/SKILL.md"
ls -la "$HOME/.agents/skills/implement"
```

Le lien doit cibler
`<FACTORY_HOME>/adapters/codex/skills/implement`. Les projets ne copient pas les
Skills et les adapters ne recopient pas les workflows du Core.

Codex découvre les Skills au démarrage. Après une installation ou une mise à
jour, fermer complètement la session en cours puis en ouvrir une nouvelle.

## 4. Préparer le projet

Depuis la racine contenant `.ai/project.yaml`, vérifier les fichiers suivants :

```text
AGENTS.md
.ai/project.yaml
.ai/repository-map.yaml
.codex/config.toml
.codex/rules/factory.rules
```

Pour un projet qui n'a pas encore les fichiers Codex :

```bash
mkdir -p .codex/rules
cp "$GAD_AI_FACTORY_HOME/templates/project/.codex/config.toml" \
  .codex/config.toml
cp "$GAD_AI_FACTORY_HOME/templates/project/.codex/rules/factory.rules" \
  .codex/rules/factory.rules
```

Reviewer et commiter ces fichiers avec la configuration projet. Ne jamais y
placer de token, mot de passe ou endpoint secret.

Pour un projet sans task manager ou MCP, vérifier également :

```yaml
integrations: {}
taskTracking:
  mode: local
```

`local` conserve toutes les exigences de traçabilité dans `.ai/runtime`, y
compris lorsque la policy calcule `required`. `external` exige au contraire un
`task-provider` et une référence liée. Codex ne doit jamais décider lui-même de
changer ce mode.

Codex ne charge la configuration `.codex/` d'un projet qu'après établissement
de la confiance pour ce repository. Accepter cette confiance uniquement après
inspection du repository, de `AGENTS.md`, de `.codex/config.toml` et des règles.

## 5. Démarrer Codex

Toujours démarrer depuis la racine du workspace Factory :

```bash
cd "/absolute/path/to/project"
codex
```

Dans la session, parcourir les Skills disponibles avec `/skills`, puis lancer
une première analyse non mutante :

```text
$analyze Analyse l'architecture actuelle sans modifier le code.
```

Les intentions disponibles sont :

| Intention | Invocation Codex | Workflow Factory |
| --- | --- | --- |
| Analyse | `$analyze ...` | `analyze-task` |
| Implémentation | `$implement ...` | `implement-task` |
| Correction | `$fix ...` | `fix-bug` |
| Refactoring | `$refactor ...` | `refactor-code` |
| Tests | `$test ...` | `add-tests` |
| Review | `$review ...` | `review-change` |
| Documentation | `$document ...` | `update-documentation` |
| Capitalisation | `$promote ...` | `promote-knowledge` |

## 6. Ce que doit faire l'adapter

Pour `$implement`, le Skill Codex appelle le Runtime commun avec l'intention et
le workflow attendus :

```text
$implement <demande>
  ↓
Codex Skill implement
  ↓
aief run --agent codex --intent implement
         --expect-workflow implement-task
  ↓
reçu Runtime persistant
  ↓
boucle execution next / complete-phase
```

Avant toute lecture approfondie du code ou modification, la sortie doit
contenir un reçu réel similaire à :

```yaml
runtimeReceipt: created
execution: <execution-id>
intent: implement
workflow:
  id: implement-task
nextPhase: understand
taskLog: <project>/.ai/runtime/tasks/<task-id>/events.jsonl
```

`Successfully loaded skill` indique seulement que Codex a chargé le fichier
`SKILL.md`. Ce message ne prouve pas que la Task ou l'Execution existe. Sans
reçu Runtime, l'agent doit s'arrêter avant de modifier le code.

Les Skills internes du Core ne sont pas des Skills natifs Codex. L'adapter ne
doit donc jamais tenter `$understand`, `$analyze-impact` ou `$create-plan`. Il
lit les contrats renvoyés par `aief execution next`.

## 7. Permissions Codex

La baseline projet utilise :

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false
```

Les règles de `.codex/rules/factory.rules` autorisent les inspections
déterministes, demandent une confirmation pour les actions gouvernées et
interdisent les commandes Git destructrices. Vérifier les décisions avant
adoption :

```bash
codex execpolicy check --pretty \
  --rules .codex/rules/factory.rules \
  -- git reset --hard HEAD

codex execpolicy check --pretty \
  --rules .codex/rules/factory.rules \
  -- aief execution approve exec-example
```

Le résultat attendu est respectivement `forbidden` puis `prompt`. Une
approbation native Codex ne remplace jamais un gate humain Factory.

Les appels Runtime générés par l'adapter doivent contenir des arguments
littéraux :

```bash
aief execution next <execution-id> \
  --project "/absolute/path/to/project" \
  --factory "/absolute/path/to/factory" \
  --json
```

Ne pas utiliser `$(pwd)`, `${GAD_AI_FACTORY_HOME}`, `cd ... &&`, une
redirection ou un pipe dans ces commandes. Ces constructions empêchent
l'analyse statique fiable et provoquent des demandes de permission inutiles.

## 8. Vérifier l'exécution

Dans un autre terminal, inspecter l'état persistant :

```bash
aief task log <task-id> \
  --project "/absolute/path/to/project" \
  --factory "/absolute/path/to/factory"

aief execution inspect <execution-id> \
  --project "/absolute/path/to/project" \
  --factory "/absolute/path/to/factory"
```

Le journal sous `.ai/runtime/tasks/<task-id>/events.jsonl` doit montrer
l'intention, le workflow, les phases, les décisions de policy, les gates et les
validations. La conversation Codex n'est pas la source de vérité.

## 9. Dépannage

### `Unrecognized command '/implement'`

Ce comportement est normal dans Codex : utiliser `$implement`, pas
`/implement`.

### `$implement` n'est pas proposé ou chargé

Vérifier :

```bash
test -f "$HOME/.agents/skills/implement/SKILL.md"
ls -la "$HOME/.agents/skills/implement"
test -f "$GAD_AI_FACTORY_HOME/adapters/codex/runtime-protocol.md"
```

Si nécessaire, réinstaller l'adapter avec `setup-adapter ... --execute`, fermer
Codex, puis relancer une nouvelle session depuis la racine du projet.

### Le Skill est chargé mais aucune Execution n'existe

Arrêter toute modification. Vérifier `aief`, `GAD_AI_FACTORY_HOME`,
`.ai/project.yaml` et la version de Factory demandée. Le Skill doit obtenir un
`runtimeReceipt`; une affirmation conversationnelle ne suffit pas.

### La configuration `.codex/` semble ignorée

Vérifier que Codex a déclaré le repository de confiance, que la session a été
démarrée à la bonne racine et qu'elle a été relancée après la modification de
la configuration.

### Codex demande une permission à chaque commande Factory

Vérifier les règles projet, puis contrôler que l'adapter utilise des chemins
absolus littéraux. Une commande contenant `$(pwd)` ou `${...}` ne correspond
pas proprement aux règles déterministes.

### `PROVIDER_NOT_CONFIGURED` alors qu'aucun task manager n'est souhaité

Vérifier `.ai/project.yaml`. La configuration attendue est :

```yaml
taskTracking:
  mode: local
integrations: {}
```

Après modification et review, demander à Codex de reprendre la même Execution.
L'adapter appelle `aief execution next`; le Runtime réévalue la décision locale
et retire l'ancien blocage. Ne jamais modifier manuellement les fichiers sous
`.ai/runtime`.

Si le blocage suivant devient `workspace-preparation-required`, la
configuration de tracking est correcte : Codex doit maintenant préparer le
worktree via `aief workspace prepare ... --execute`, après l'autorisation
native attendue.

### `url is not supported for stdio`

Le bloc `gitlab` contient probablement à la fois une ancienne configuration
HTTP (`url`) et une configuration STDIO (`command`). Supprimer le doublon et
conserver une seule définition `mcp_servers.gitlab`. Les configurations
utilisateur (`~/.codex/config.toml`) et projet (`.codex/config.toml`) portant le
même nom peuvent être fusionnées par Codex et produire cette erreur.

Pour l'authentification OAuth GitLab avec les versions Codex concernées par
`Authorization server issuer mismatch`, le bloc attendu est :

```toml
[mcp_servers.gitlab]
command = "npx"
args = ["-y", "mcp-remote@0.1.26", "https://gitlab.com/api/v4/mcp", "--static-oauth-client-metadata", '{"scope":"mcp"}']
```

La version `mcp-remote` est figée pour rendre le démarrage reproductible. Avec
ce transport, ne pas lancer `codex mcp login gitlab` : le navigateur OAuth est
ouvert par le pont au démarrage de Codex.

### `404 Not Found` avec GitLab MCP

L'URL `https://gitlab.com/api/v4/mcp` est l'URL officielle. Sur GitLab.com, un
`404` après l'authentification indique généralement que le serveur MCP n'est
pas activé pour un groupe racine auquel l'utilisateur appartient. Un Owner doit
activer GitLab Duo, les fonctionnalités beta/expérimentales et l'accès MCP sur
le groupe racine. L'activation dans un sous-groupe seul ne suffit pas.

### Cache OAuth MCP obsolète

Si une ancienne autorisation est réutilisée, nettoyer uniquement le cache du
pont puis relancer Codex :

```bash
rm -rf ~/.mcp-auth/mcp-remote*
```

## 10. Checklist minimale

- [ ] `GAD_AI_FACTORY_HOME` pointe vers la version attendue.
- [ ] `aief` est disponible dans le `PATH`.
- [ ] `~/.agents/skills/implement/SKILL.md` existe.
- [ ] La session Codex a été redémarrée après installation des Skills.
- [ ] Codex est lancé depuis la racine contenant `.ai/project.yaml`.
- [ ] `taskTracking.mode` correspond au système de traçabilité réellement voulu.
- [ ] En mode `external`, un `task-provider` est configuré ; en mode `local`,
      `.ai/runtime` est disponible et ignoré par Git.
- [ ] Le repository et sa configuration `.codex/` ont été inspectés puis
      déclarés de confiance.
- [ ] `$analyze` crée un reçu Runtime et ne modifie pas le code.
- [ ] `$implement` résout `implement-task` et commence par `understand`.
- [ ] Les logs apparaissent dans `.ai/runtime/tasks/<task-id>/events.jsonl`.
- [ ] `/implement` n'est jamais utilisé dans Codex.

## 11. Références officielles OpenAI

- Skills Codex : <https://developers.openai.com/codex/skills>
- Configuration Codex : <https://developers.openai.com/codex/config-basic>
- Règles de commandes : <https://developers.openai.com/codex/rules>
- Instructions `AGENTS.md` : <https://developers.openai.com/codex/guides/agents-md>
