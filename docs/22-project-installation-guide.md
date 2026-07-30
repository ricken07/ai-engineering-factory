# 22 — Installer l’AI Engineering Factory dans un projet

Ce document est la procédure cible pour raccorder un projet existant à l’AI Engineering Factory. La Factory reste installée une seule fois sur le poste du développeur ; le projet reçoit uniquement son template `.ai/` et ses fichiers de bootstrap agent.

Après installation, poursuivre avec
[`23-first-steps.md`](23-first-steps.md) pour le parcours quotidien depuis Claude
Code ou Codex.

Les exemples utilisent la version `1.13.0`. Remplacez les valeurs entre `<...>` avant exécution.

## 0.1 Rendre la Factory visible au processus agent

Le projet référence le nom d’une variable, pas un chemin propre à une machine :

```yaml
factory:
  version: 1.13.0
  homeEnv: GAD_AI_FACTORY_HOME
```

Le poste développeur fournit sa valeur :

```bash
export GAD_AI_FACTORY_HOME="<ABSOLUTE_FACTORY_INSTALLATION>"
```

Exemple local :

```bash
export GAD_AI_FACTORY_HOME="/Users/example/.gad/ai-engineering-factory/1.13.0"
```

### `.zshrc` ne suffit pas dans tous les modes de lancement

`.zshrc` est chargé par un shell Zsh interactif. La variable peut être absente
si Claude Code ou Codex est lancé :

- depuis un IDE ou une application graphique ;
- depuis un shell non interactif ;
- avant l’ajout de l’export ;
- depuis une session qui n’a pas rechargé sa configuration.

Pour les nouveaux shells login Zsh, déclarer également la variable dans
`~/.zprofile`, ou utiliser le mécanisme d’environnement géré par
l’organisation :

```bash
export GAD_AI_FACTORY_HOME="<ABSOLUTE_FACTORY_INSTALLATION>"
```

Ouvrir ensuite un nouveau terminal, ou recharger explicitement :

```bash
source "$HOME/.zshrc"
printenv GAD_AI_FACTORY_HOME
test -f "$GAD_AI_FACTORY_HOME/factory.yaml"
```

Lancer l’agent depuis ce même terminal garantit l’héritage :

```bash
cd "<PROJECT_ROOT>"
env | grep '^GAD_AI_FACTORY_HOME='
claude
# ou : codex
```

### Configuration locale Claude Code

Lorsqu’un agent est lancé depuis un IDE ou qu’un chemin est spécifique au
poste, Claude Code peut recevoir la variable via le fichier local non versionné
`.claude/settings.local.json` :

```json
{
  "env": {
    "GAD_AI_FACTORY_HOME": "<ABSOLUTE_FACTORY_INSTALLATION>"
  }
}
```

Si ce fichier contient déjà des permissions, fusionner la clé `env` sans
écraser `permissions`. Ne pas placer ce chemin local dans
`.claude/settings.json`, qui est partagé et commité. Ne jamais stocker de secret
dans ces fichiers.

### Contrôle depuis la session agent

Avant le premier workflow, faire exécuter uniquement :

```bash
printenv GAD_AI_FACTORY_HOME
test -f "$GAD_AI_FACTORY_HOME/factory.yaml"
```

Une sortie vide est un échec de précondition. L’adapter doit s’arrêter et
indiquer comment configurer l’environnement. Il ne doit jamais chercher une
installation arbitraire, ni copier, générer ou lier `factory.yaml` dans le
workspace projet.

## 1. Résultat attendu

```text
Poste développeur
├── ~/.gad/ai-engineering-factory/1.13.0/  # Factory centrale, en lecture seule
├── ~/.agents/skills/                      # Entrées Codex vers la Factory
└── ~/.claude/skills/                      # Entrées Claude Code vers la Factory

Workspace projet
├── .ai/                                   # Configuration et connaissance du projet
├── .claude/settings.json                  # Permissions Claude partagées
├── .codex/config.toml                     # Sandbox/approbations Codex
├── .codex/rules/factory.rules             # Règles de commandes Codex
├── AGENTS.md                              # Bootstrap commun/Codex, concis
└── CLAUDE.md                              # Pont Claude vers AGENTS.md
```

Le Core, les workflows et les skills ne sont jamais copiés dans le projet.

Les permissions sont des garde-fous natifs complémentaires. Elles ne remplacent
ni `PolicyDecision`, ni les niveaux d’autonomie, ni les human gates. Le template
prêt à reviewer et les adaptations par stack sont documentés dans
[`25-agent-permissions.md`](25-agent-permissions.md).

### Quand l’installation est-elle réellement effective ?

La présence de `.ai/project.yaml` signifie seulement que le projet est
**configuré**. La Factory est **opérationnelle** lorsque les cinq couches
suivantes sont vérifiées :

| Couche | Vérification attendue |
| --- | --- |
| Factory centrale | Le tag demandé existe dans `GAD_AI_FACTORY_HOME` |
| Runtime | `aief` est installé et accessible dans le `PATH` |
| Adapter | Les skills existent dans `~/.agents/skills` ou `~/.claude/skills` |
| Projet | `.ai/project.yaml`, `AGENTS.md` et `CLAUDE.md` sont présents à la racine |
| Session | L’agent a été redémarré après l’installation des skills |

Un projet peut donc réussir `aief validate` tout en affichant
`No commands match "/implement"` si l’adapter Claude Code n’est pas installé.

## 1.1 Expérience quotidienne cible

Après l’installation initiale, le développeur ne lance pas `aief run` pour travailler.
Il démarre son agent depuis la racine du workspace :

```bash
# La présence de .ai/project.yaml permet la découverte du projet Factory.
cd "<ABSOLUTE_PROJECT_WORKSPACE>"

# Choisir l’un des deux agents.
codex
# ou
claude
```

Puis il utilise une intention explicite :

```text
Codex      $implement TASK-123
Claude     /implement TASK-123
```

ou du langage naturel :

```text
Implémente TASK-123.
Corrige le problème de reprise d’apprentissage décrit dans l’audit.
Refactore PaymentOrchestrator sans modifier son comportement.
Analyse ce module sans modifier le code.
```

Dans les deux cas, l’adapter transmet la demande intacte au Runtime commun. Le
Runtime normalise l’intention, crée ou reprend la Task et l’Execution, applique
les policies et renvoie à l’agent la prochaine phase à exécuter.

```text
Développeur
    ↓ commande native ou texte libre
Claude/Codex
    ↓ adapter installé
aief Runtime
    ↓ Task → Workflow → Phases → Gates → Artifacts
Claude/Codex
    ↓ raisonnement, code, tests et compte rendu
Développeur
```

La CLI `aief` reste nécessaire, mais comme dépendance interne des adapters et
comme outil d’administration (`validate`, `doctor`, inspection, reprise). Elle
n’est pas l’interface quotidienne de saisie des tâches.

## 2. Pré-requis

Vérifier Git et Python :

```bash
# Git est nécessaire pour installer/versionner la Factory et protéger les workspaces.
git --version

# Python 3.11 ou supérieur est requis par la CLI aief.
python3 --version
```

Installer `uv` si la commande n’existe pas :

```bash
# Installateur officiel uv pour macOS/Linux. En entreprise, utiliser le canal approuvé.
curl -LsSf https://astral.sh/uv/install.sh | sh

# Recharge le PATH de la session courante si l’installateur le demande.
source "$HOME/.local/bin/env"

# Confirme que le gestionnaire d’outils est disponible.
uv --version
```

## 3. Installer une version centrale de la Factory

Définir les paramètres de l’installation :

```bash
# URL du repository central de l’organisation.
export AIEF_REPOSITORY_URL="<FACTORY_GIT_URL>"

# Version immuable demandée par les projets.
export AIEF_VERSION="1.13.0"

# Racine organisationnelle locale. Ce dossier n’appartient à aucun projet métier.
export AIEF_INSTALL_ROOT="$HOME/.gad/ai-engineering-factory"

# Chemin final de la version installée.
export AIEF_HOME="$AIEF_INSTALL_ROOT/$AIEF_VERSION"
```

Cloner et figer la version :

```bash
# Crée uniquement le répertoire parent ; ne remplace aucune installation existante.
mkdir -p "$AIEF_INSTALL_ROOT"

# Clone la Factory dans un dossier dédié à la version.
git clone "$AIEF_REPOSITORY_URL" "$AIEF_HOME"

# Se place dans la Factory pour vérifier le tag demandé.
cd "$AIEF_HOME"

# Récupère les tags, puis positionne l’installation sur la version immuable.
git fetch --tags
git checkout "v$AIEF_VERSION"

# Vérifie que HEAD correspond bien au tag attendu.
git describe --tags --exact-match
```

Pour un développement local de la Factory, `AIEF_HOME` peut temporairement pointer vers son clone de travail. Cette variante ne doit pas servir d’installation partagée stable.

## 4. Installer la CLI `aief`

```bash
# Installe la CLI comme outil isolé. Le développeur ne gère ni venv ni pip.
uv tool install "$AIEF_HOME"

# Confirme que l’exécutable est disponible.
aief --help

# Affiche l’exécutable réellement utilisé, par exemple ~/.local/bin/aief.
command -v aief
```

Pendant le développement de la Factory uniquement :

```bash
# Le mode editable reflète immédiatement les changements du clone de travail.
uv tool install --force --editable "$AIEF_HOME"
```

Déclarer le chemin de résolution des assets Factory :

```bash
# Utilisé par les bootstraps/adapters pour retrouver la version centrale.
export GAD_AI_FACTORY_HOME="$AIEF_HOME"

# Rend la variable persistante pour les nouvelles sessions Zsh.
echo "export GAD_AI_FACTORY_HOME=\"$AIEF_HOME\"" >> "$HOME/.zshrc"
source "$HOME/.zshrc"

# Vérifie que la session courante résout la Factory et ses assets.
test -n "$GAD_AI_FACTORY_HOME"
test -d "$GAD_AI_FACTORY_HOME/core"
test -f "$GAD_AI_FACTORY_HOME/pyproject.toml"
```

## 5. Installer les adapters agents

Toujours examiner le dry-run avant de modifier les emplacements utilisateur :

```bash
# Prévisualise les liens vers les skills Codex, sans écriture.
aief setup-adapter codex --factory "$AIEF_HOME"

# Prévisualise les liens vers les skills Claude Code, sans écriture.
aief setup-adapter claude-code --factory "$AIEF_HOME"
```

Si le plan est correct :

```bash
# Installe les entrées Codex sous ~/.agents/skills/.
aief setup-adapter codex --factory "$AIEF_HOME" --execute

# Installe les entrées Claude Code sous ~/.claude/skills/.
aief setup-adapter claude-code --factory "$AIEF_HOME" --execute
```

Les adapters restent minces : `$implement` côté Codex et `/implement` côté Claude déclenchent le même workflow du Core.

Vérifier physiquement l’installation :

```bash
# Doit trouver le manifeste du skill Codex.
test -f "$HOME/.agents/skills/implement/SKILL.md"

# Doit trouver le manifeste du skill Claude Code.
test -f "$HOME/.claude/skills/implement/SKILL.md"

# Affiche les liens vers la Factory centrale lorsqu’ils sont installés en symlink.
ls -la "$HOME/.agents/skills/implement"
ls -la "$HOME/.claude/skills/implement"
```

Si l’un de ces tests échoue, l’agent correspondant ne pourra pas découvrir sa
commande native `implement`.

## 6. Initialiser le projet

Définir le workspace cible :

```bash
# Doit pointer vers la racine commune contenant les repositories du projet.
export PROJECT_ROOT="<ABSOLUTE_PROJECT_WORKSPACE>"

# Refuse implicitement une mauvaise cible lors des commandes suivantes.
test -d "$PROJECT_ROOT"
```

Pour un projet neuf sans configuration `.ai/` :

```bash
# Vérifie que la cible n’existe pas afin de ne rien écraser.
test ! -e "$PROJECT_ROOT/.ai"

# Copie uniquement le contexte projet. Le Core reste centralisé.
cp -R "$AIEF_HOME/templates/project/.ai" "$PROJECT_ROOT/.ai"
```

Les éventuels `AGENTS.md` et `CLAUDE.md` existants doivent être analysés et fusionnés manuellement. Ne les écrasez jamais avec une copie aveugle.

Si ces fichiers n’existent pas encore, installer les bootstraps du template :

```bash
# Les gardes empêchent tout écrasement d’instructions existantes.
test ! -e "$PROJECT_ROOT/AGENTS.md"
test ! -e "$PROJECT_ROOT/CLAUDE.md"

cp "$AIEF_HOME/templates/project/AGENTS.md" "$PROJECT_ROOT/AGENTS.md"
cp "$AIEF_HOME/templates/project/CLAUDE.md" "$PROJECT_ROOT/CLAUDE.md"

# Confirme que le lancement depuis PROJECT_ROOT exposera les deux bootstraps.
test -f "$PROJECT_ROOT/AGENTS.md"
test -f "$PROJECT_ROOT/CLAUDE.md"
```

Pour un fichier existant, fusionner uniquement les instructions Factory après
revue humaine. `CLAUDE.md` doit importer `AGENTS.md` avec `@AGENTS.md` afin
d’éviter deux copies divergentes.

## 7. Configurer `.ai/project.yaml`

Exemple poly-repo commenté :

```yaml
apiVersion: factory.gaddigital.io/v1alpha1 # Version du contrat, pas de la Factory.
kind: Project

metadata:
  id: my-project                         # Identifiant stable, sans espace.
  name: My Project                       # Nom destiné aux humains.

factory:
  version: 1.13.0                        # Version centrale exigée par le projet.
  homeEnv: GAD_AI_FACTORY_HOME           # Variable qui localise son installation.

workspace:
  strategy: polyrepo                     # Utiliser monorepo si une seule racine Git.
  root: .                                # Racine relative au fichier projet.

workspaceSafety:
  mode: worktree                         # Isole les changements de l’agent.
  baseBranch: main                       # Branche cible par défaut.
  taskBranchPrefix: aief                 # Préfixe des branches de travail Factory.

repositories:
  - id: backend
    path: ./backend                      # Doit rester dans le workspace.
    role: backend-application
    profiles: [java, spring, maven]      # Connaissance technique, jamais dans Core.
    responsibilities: [business-domain, rest-api]
    dependencies: []
    criticalDomains: [authentication, personal-data]
    git:
      baseBranch: main

  - id: frontend
    path: ./frontend
    role: web-application
    profiles: [node, react]
    responsibilities: [user-interface]
    dependencies:
      - repository: backend
        type: REST
    criticalDomains: [authentication]
    git:
      baseBranch: main

context:
  project: .ai/context/project.md
  architecture: .ai/context/architecture.md
  domain: .ai/context/domain.md
  conventions: .ai/context/conventions.md
  decisions: .ai/decisions
  memory: .ai/memory/shared.md

runtime:
  root: .ai/runtime                      # État déterministe Task/Execution/Handoff.
  taskRetentionDays: 30
  executionRetentionDays: 14

integrations: {}                         # Démarrage sans MCP ni provider externe.

taskTracking:
  mode: local                            # .ai/runtime suffit ; aucun task-provider requis.

autonomy:
  default: L2                            # Lecture, modifications locales et tests.
  maximum: L2                            # Interdit commit/push/MR automatique au pilote.

policyRefs: []                           # Policies projet additionnelles si nécessaires.

engineering:
  inheritOrganization: true              # Hérite standards/pratiques organisationnels.
  organizationCatalogs:                  # Catalogues choisis par ce projet.
    - factory-default@1.0.0
  practices: {}                          # Activations/surcharges explicites du projet.
```

Principes de configuration :

- déclarer chaque repository Git réellement piloté ;
- ne pas déclarer un dossier uniquement documentaire comme repository exécutable ;
- utiliser les profiles existants dans `profiles/` ;
- sélectionner explicitement les catalogues organisationnels applicables ;
- commencer à `L2`, puis relever l’autonomie après retour d’expérience ;
- choisir explicitement `taskTracking.mode: local` sans gestionnaire de tâches,
  ou `external` lorsqu’un `task-provider` doit devenir la référence canonique ;
- ne placer aucun secret, endpoint ou token dans ce fichier.

Exemples de sélection :

```yaml
# Socle fourni par la Factory.
organizationCatalogs: [factory-default@1.0.0]

# Exemple d'organisation qui étend le socle Factory.
organizationCatalogs: [example-organization@1.0.0]

# Projet autonome : aucune convention d’organisation implicite.
organizationCatalogs: []
```

Une autre organisation ajoute son propre `OrganizationCatalog` sans modifier
le Core ni les Profiles. Voir
[`24-organization-knowledge-catalog.md`](24-organization-knowledge-catalog.md).

## 8. Configurer la topologie

Exemple `.ai/repository-map.yaml` :

```yaml
apiVersion: factory.gaddigital.io/v1alpha1
kind: RepositoryMap

metadata:
  id: my-project-repositories

repositories:
  backend:
    responsibilities: [business-services, persistence]
    exposes: [rest-api]
    consumes: [postgresql]

  frontend:
    responsibilities: [web-ui]
    exposes: [public-web-application]
    consumes: [rest-api]

relationships:
  - from: frontend
    to: backend
    type: REST

criticalDomains:
  - authentication
  - personal-data
```

Cette carte décrit les impacts transverses. Elle ne remplace pas l’analyse du code réel.

## 9. Rédiger le contexte Markdown

Compléter au minimum :

```text
.ai/context/project.md       objectif, utilisateurs, périmètre et références stratégiques
.ai/context/architecture.md  composants, flux, dépendances et invariants
.ai/context/domain.md        vocabulaire métier, états et règles
.ai/context/conventions.md   conventions réellement spécifiques au projet
```

Règles documentaires :

- distinguer cible produit, état observé et hypothèses ;
- référencer les audits/ADRs utiles par leur chemin ;
- demander à l’agent de vérifier les rapports contre le code et les tests ;
- ne pas recopier les conventions organisationnelles déjà résolues par les profiles ;
- ne pas transformer `.ai/memory/` en documentation générale non gouvernée.

## 10. Bootstrap `AGENTS.md` et `CLAUDE.md`

`AGENTS.md` doit rester concis :

```markdown
# AI Engineering Factory Project

Before engineering work:

1. Read `.ai/project.yaml` and resolve the pinned Factory version.
2. Use Factory workflows and policies for engineering tasks.
3. Load `.ai/` context progressively.
4. Never overwrite unrelated local changes.
5. Respect human gates and persist structured runtime artifacts.
```

`CLAUDE.md` peut importer ce bootstrap partagé :

```markdown
@AGENTS.md

Use the centrally installed AI Engineering Factory Claude Code adapter.
Do not duplicate Core workflows or policies in this file.
```

Si le workspace possède déjà ces fichiers, préserver les instructions existantes et ajouter uniquement le pont Factory nécessaire.

## 11. Valider l’installation sans MCP

```bash
# Valide YAML, schemas, références, profiles et cohérence du projet.
aief validate "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Vérifie les préconditions générales du workspace.
aief doctor "$PROJECT_ROOT"

# Génère un lock vide et sans secret lorsque integrations: {}.
aief integrations lock "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Doit signaler providers: [] et toutes les vérifications en état ok.
aief integrations doctor "$PROJECT_ROOT" --factory "$AIEF_HOME"
```

Le lock vide ne configure aucun MCP. Il prouve que l’absence d’intégration est intentionnelle.

### Choisir la traçabilité sans gestionnaire de tâches

Une installation sans MCP doit aussi déclarer explicitement que la
traçabilité locale satisfait les policies :

```yaml
integrations: {}
taskTracking:
  mode: local
```

Le niveau calculé (`optional`, `recommended`, `required`) reste inchangé. Pour
une tâche critique, `required` impose toujours la Task, les artifacts, les
décisions, les validations et le journal Runtime ; il n'impose simplement pas
de ticket externe.

Ne pas utiliser `mode: external` sans `integrations.task-provider`, sauf si le
blocage `PROVIDER_NOT_CONFIGURED` est volontaire pendant l'onboarding.

| Configuration | Résultat d'un tracking `required` |
| --- | --- |
| `mode: local`, aucun provider | satisfait par `.ai/runtime` |
| `mode: external`, provider configuré et lié | satisfait par la référence externe |
| `mode: external`, provider absent | Execution bloquée |
| propriété absente | comportement conservateur `external` |

### Execution déjà bloquée par le suivi externe

Après une modification reviewée de `external` vers `local`, ne jamais éditer
`tracking.yaml` ou `execution.yaml`. Relancer simplement la résolution :

```bash
aief execution next <execution-id> \
  --project "/absolute/project" \
  --factory "/absolute/factory" \
  --json
```

Le Runtime recalcule `tracking.yaml`, marque la décision locale comme
`satisfied: true`, retire `external-tracking-required`, puis applique le
prochain contrôle. Si le projet utilise `workspaceSafety.mode: worktree`, le
nouveau blocage attendu peut être `workspace-preparation-required` :

```bash
aief workspace prepare <execution-id> \
  --project "/absolute/project" \
  --factory "/absolute/factory" \
  --execute \
  --json
```

Ce second blocage est indépendant du task manager : il protège les changements
Git locaux du développeur.

### Contrôle Go/No-Go avant de lancer un agent

Exécuter ces contrôles depuis une nouvelle session de terminal :

```bash
# 1. Runtime disponible.
command -v aief

# 2. Factory centrale résolue.
test -n "$GAD_AI_FACTORY_HOME"
test -d "$GAD_AI_FACTORY_HOME/core"

# 3. Projet et bootstraps présents.
test -f "$PROJECT_ROOT/.ai/project.yaml"
test -f "$PROJECT_ROOT/AGENTS.md"
test -f "$PROJECT_ROOT/CLAUDE.md"
test -f "$PROJECT_ROOT/.claude/settings.json"
test -f "$PROJECT_ROOT/.codex/config.toml"
test -f "$PROJECT_ROOT/.codex/rules/factory.rules"

# 4. Adapter Claude Code, si Claude sera utilisé.
test -f "$HOME/.claude/skills/implement/SKILL.md"

# 5. Adapter Codex, si Codex sera utilisé.
test -f "$HOME/.agents/skills/implement/SKILL.md"

# 6. Configuration déterministe valide.
aief validate "$PROJECT_ROOT" --factory "$GAD_AI_FACTORY_HOME"
aief doctor "$PROJECT_ROOT"
```

Tous les contrôles applicables doivent réussir. Une erreur doit être corrigée
avant d’ouvrir la première session agent.

## 12. Premier test contrôlé depuis Claude Code ou Codex

Commencer par une tâche locale et non mutante :

```bash
cd "$PROJECT_ROOT"

# Démarre l’agent choisi depuis la racine qui contient .ai/project.yaml.
codex
# ou : claude
```

Fermer toute session Claude Code ou Codex ouverte avant l’installation des
skills, puis démarrer une nouvelle session. Les commandes natives sont
découvertes au démarrage de l’agent.

Dans la session de l’agent, après installation des adapters :

```text
Codex      $analyze Analyse l’architecture actuelle sans modifier le code.
Claude     /analyze Analyse l’architecture actuelle sans modifier le code.
```

Le texte libre doit suivre exactement le même chemin :

```text
Analyse l’architecture actuelle, vérifie les documents contre le code et ne
modifie aucun fichier.
```

`aief run` est seulement utile pour diagnostiquer directement la frontière
Runtime, écrire un test automatisé d’intégration ou développer un adapter :

```bash
# Commande bas niveau ; elle ne constitue pas l’expérience développeur normale.
aief run \
  "Analyse l’architecture actuelle sans modifier le code." \
  --agent codex \
  --project "$PROJECT_ROOT" \
  --factory "$AIEF_HOME"
```

Puis tester une modification locale limitée, sur un workspace propre ou un worktree préparé par la Factory :

```text
Codex      $test Ajoute uniquement les tests manquants pour ce comportement.
Claude     /test Ajoute uniquement les tests manquants pour ce comportement.
```

### Diagnostic de `No commands match "/implement"`

Ce message indique que Claude Code n’a pas découvert le skill. Il ne signifie
pas nécessairement que `.ai/project.yaml` est invalide.

Vérifier dans cet ordre :

```bash
# 1. Le skill Claude est-il réellement installé ?
test -f "$HOME/.claude/skills/implement/SKILL.md"

# 2. Le lien éventuel pointe-t-il vers une cible existante ?
ls -la "$HOME/.claude/skills/implement"

# 3. La Factory centrale est-elle résolue dans cette session ?
printenv GAD_AI_FACTORY_HOME
test -f "$GAD_AI_FACTORY_HOME/adapters/claude-code/runtime-protocol.md"

# 4. Les instructions projet existent-elles à la racine de lancement ?
test -f "$PROJECT_ROOT/CLAUDE.md"
test -f "$PROJECT_ROOT/AGENTS.md"
```

Si le skill manque :

```bash
aief setup-adapter claude-code \
  --factory "$GAD_AI_FACTORY_HOME" \
  --execute
```

Quitter ensuite complètement Claude Code et le relancer depuis la racine :

```bash
cd "$PROJECT_ROOT"
claude
```

Pour Codex, remplacer `~/.claude/skills/implement` par
`~/.agents/skills/implement`, installer l’adapter `codex`, puis relancer
`codex`. Dans Codex, l'invocation correcte est `$implement`; `/implement`
retourne normalement `Unrecognized command` parce que `/` désigne les commandes
intégrées du client. Le parcours complet et le dépannage Codex sont documentés
dans [`27-codex-usage.md`](27-codex-usage.md).

## 13. Activer ultérieurement un provider MCP

Le provider doit d'abord exister dans le catalogue central de la Factory et être
autorisé par la gouvernance de l'organisation. Le projet ne configure pas le
MCP : il active uniquement une association logique entre capability et
provider.

```text
Factory integrations/   définition technique et opérations
Organization            providers autorisés et valeurs par défaut
Project                 activation des capabilities
Adapter                 génération Claude/Codex
Developer runtime       authentification locale
```

Le projet choisit donc une capability et un provider, jamais un transport, une
URL, une commande, un header ou un token :

```yaml
taskTracking:
  mode: external       # Seulement si Jira/GitLab/GitHub doit porter les Tasks requises.

integrations:
  task-provider:
    provider: jira
  source-control:
    provider: gitlab
  knowledge-base:
    provider: confluence
```

Configuration interdite dans `.ai/project.yaml` :

```yaml
integrations:
  gitlab:
    url: https://gitlab.example/mcp  # interdit
    transport: http                  # interdit
    token: glpat-secret              # strictement interdit
```

Un projet peut conserver `taskTracking.mode: local` tout en activant
`source-control` ou `knowledge-base`. La présence d'un MCP n'impose pas le mode
external ; seul le choix du système canonique de Task le détermine.

Puis :

```bash
# Fige les définitions d’intégration sélectionnées, sans secret.
aief integrations lock "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Vérifie catalogues, capabilities, MCP et variables requises.
aief integrations doctor "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Prévisualise la configuration native Codex ; aucune écriture sans --execute.
aief integrations sync codex "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Applique après revue explicite du plan. Pour un provider organisationnel
# partagé, préférer le scope user afin d'éviter une configuration par projet.
aief integrations sync codex "$PROJECT_ROOT" --factory "$AIEF_HOME" --scope user --execute

# Même procédure pour Claude Code.
aief integrations sync claude-code "$PROJECT_ROOT" --factory "$AIEF_HOME"
aief integrations sync claude-code "$PROJECT_ROOT" --factory "$AIEF_HOME" --scope user --execute
```

`sync` matérialise la configuration native ; il ne déplace pas la source de
vérité dans le client. Pour un MCP spécifique au projet et explicitement
autorisé, le scope `project` peut être utilisé après validation de la policy
organisationnelle.

Les endpoints gérés et credentials restent dans une configuration d'entreprise,
le keychain, un secret manager, le magasin d'authentification de l'agent ou
l'environnement. Ils ne sont jamais commités dans `.ai/`, `.mcp.json` ou
`.codex/config.toml`.

### MCP propre au projet

Un projet ne peut pas déclarer arbitrairement un serveur personnalisé. La
gouvernance organisationnelle doit autoriser les MCP custom, leurs transports,
leurs scopes et, si nécessaire, imposer une approbation humaine. Tant que ce
contrat n'est pas pris en charge par le Runtime, ajouter manuellement un serveur
dans `.mcp.json` ou `.codex/config.toml` ne constitue pas une intégration
Factory valide.

## 14. Mise à niveau de la Factory

Une montée de version est explicite :

1. installer le nouveau tag dans un nouveau dossier central ;
2. mettre à jour `factory.version` dans `.ai/project.yaml` sur une branche projet ;
3. repointer `GAD_AI_FACTORY_HOME` vers cette installation ;
4. réinstaller/repointer les adapters ;
5. régénérer l’integration lock ;
6. exécuter `validate` et `doctor` ;
7. tester un workflow non mutant avant une implémentation.

Ne remplacez pas silencieusement le contenu d’un dossier de version existant.

## 15. Checklist d’acceptation

- [ ] La Factory est installée depuis un tag connu.
- [ ] `GAD_AI_FACTORY_HOME` pointe vers cette version.
- [ ] `aief --help` fonctionne sans environnement Python manuel.
- [ ] Les adapters ont été prévisualisés puis installés explicitement.
- [ ] Les permissions natives Claude/Codex ont été revues et commitées.
- [ ] Les validations propres aux Profiles ont des préfixes précis, sans autorisation shell globale.
- [ ] Les gates, écritures externes et publications Git restent interactifs.
- [ ] `.ai/project.yaml` décrit tous les repositories pilotés.
- [ ] Les profiles correspondent aux technologies réellement détectées.
- [ ] `.ai/repository-map.yaml` décrit les dépendances inter-repositories.
- [ ] Les documents de contexte distinguent état réel, cible et hypothèses.
- [ ] L’autonomie initiale et les domaines critiques sont explicites.
- [ ] Aucun secret n’est stocké dans le repository.
- [ ] `aief validate` et `aief doctor` réussissent.
- [ ] `aief integrations doctor` réussit, y compris sans provider.
- [ ] Le premier test est une analyse non mutante.
- [ ] Le reçu Runtime contient `execution`, `workflow`, `nextPhase` et `taskLog`.
- [ ] `aief task log <task-id>` montre `task.normalized` et `workflow.started`.
- [ ] Les modifications locales préexistantes ne sont ni écrasées ni incorporées.
