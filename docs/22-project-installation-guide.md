# 22 — Installer l’AI Engineering Factory dans un projet

Ce document est la procédure cible pour raccorder un projet existant à l’AI Engineering Factory. La Factory reste installée une seule fois sur le poste du développeur ; le projet reçoit uniquement son template `.ai/` et ses fichiers de bootstrap agent.

Après installation, poursuivre avec
[`23-first-steps.md`](23-first-steps.md) pour le parcours quotidien depuis Claude
Code ou Codex.

Les exemples utilisent la version `1.11.0`. Remplacez les valeurs entre `<...>` avant exécution.

## 1. Résultat attendu

```text
Poste développeur
├── ~/.gad/ai-engineering-factory/1.11.0/  # Factory centrale, en lecture seule
├── ~/.agents/skills/                      # Entrées Codex vers la Factory
└── ~/.claude/skills/                      # Entrées Claude Code vers la Factory

Workspace projet
├── .ai/                                   # Configuration et connaissance du projet
├── AGENTS.md                              # Bootstrap commun/Codex, concis
└── CLAUDE.md                              # Pont Claude vers AGENTS.md
```

Le Core, les workflows et les skills ne sont jamais copiés dans le projet.

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
export AIEF_VERSION="1.11.0"

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

## 7. Configurer `.ai/project.yaml`

Exemple poly-repo commenté :

```yaml
apiVersion: factory.gaddigital.io/v1alpha1 # Version du contrat, pas de la Factory.
kind: Project

metadata:
  id: my-project                         # Identifiant stable, sans espace.
  name: My Project                       # Nom destiné aux humains.

factory:
  version: 1.11.0                        # Version centrale exigée par le projet.
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

autonomy:
  default: L2                            # Lecture, modifications locales et tests.
  maximum: L2                            # Interdit commit/push/MR automatique au pilote.

policyRefs: []                           # Policies projet additionnelles si nécessaires.

engineering:
  inheritOrganization: true              # Hérite standards/pratiques organisationnels.
  practices: {}                          # Activations/surcharges explicites du projet.
```

Principes de configuration :

- déclarer chaque repository Git réellement piloté ;
- ne pas déclarer un dossier uniquement documentaire comme repository exécutable ;
- utiliser les profiles existants dans `profiles/` ;
- commencer à `L2`, puis relever l’autonomie après retour d’expérience ;
- ne placer aucun secret, endpoint ou token dans ce fichier.

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

## 12. Premier test contrôlé depuis Claude Code ou Codex

Commencer par une tâche locale et non mutante :

```bash
cd "$PROJECT_ROOT"

# Démarre l’agent choisi depuis la racine qui contient .ai/project.yaml.
codex
# ou : claude
```

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

## 13. Activer ultérieurement un provider MCP

Le projet choisit une capability et un provider, pas un transport ni un token :

```yaml
integrations:
  task-provider:
    provider: jira
  source-control:
    provider: gitlab
  knowledge-base:
    provider: confluence
```

Puis :

```bash
# Fige les définitions d’intégration sélectionnées, sans secret.
aief integrations lock "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Vérifie catalogues, capabilities, MCP et variables requises.
aief integrations doctor "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Prévisualise la configuration native Codex ; aucune écriture sans --execute.
aief integrations sync codex "$PROJECT_ROOT" --factory "$AIEF_HOME"

# Applique après revue explicite du plan.
aief integrations sync codex "$PROJECT_ROOT" --factory "$AIEF_HOME" --scope project --execute

# Même procédure pour Claude Code.
aief integrations sync claude-code "$PROJECT_ROOT" --factory "$AIEF_HOME"
aief integrations sync claude-code "$PROJECT_ROOT" --factory "$AIEF_HOME" --scope project --execute
```

Les endpoints et credentials restent dans l’environnement, le keychain, un secret manager ou une configuration d’entreprise. Ils ne sont jamais commités dans `.ai/`, `.mcp.json` ou `.codex/config.toml`.

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
- [ ] `.ai/project.yaml` décrit tous les repositories pilotés.
- [ ] Les profiles correspondent aux technologies réellement détectées.
- [ ] `.ai/repository-map.yaml` décrit les dépendances inter-repositories.
- [ ] Les documents de contexte distinguent état réel, cible et hypothèses.
- [ ] L’autonomie initiale et les domaines critiques sont explicites.
- [ ] Aucun secret n’est stocké dans le repository.
- [ ] `aief validate` et `aief doctor` réussissent.
- [ ] `aief integrations doctor` réussit, y compris sans provider.
- [ ] Le premier test est une analyse non mutante.
- [ ] Les modifications locales préexistantes ne sont ni écrasées ni incorporées.
