# 23 — Premiers pas dans un projet Factory

Ce guide commence après l’installation décrite dans
[`22-project-installation-guide.md`](22-project-installation-guide.md).
Les prompts d’autorisation attendus et les modèles projet sont détaillés dans
[`25-agent-permissions.md`](25-agent-permissions.md).

## 1. Ce que lance le développeur

Le développeur démarre Claude Code ou Codex depuis la racine qui contient
`.ai/project.yaml` :

```bash
cd "<PROJECT_ROOT>"

# Une session Codex
codex

# Ou une session Claude Code
claude
```

Il ne lance pas `aief run`. L’adapter installé le fait automatiquement et pilote
la boucle Runtime pour le compte de l’agent.

## 2. Commande native ou texte libre

Les commandes natives rendent l’intention explicite :

| Intention | Codex | Claude Code |
| --- | --- | --- |
| Analyser | `$analyze TASK-123` | `/analyze TASK-123` |
| Implémenter | `$implement TASK-123` | `/implement TASK-123` |
| Corriger | `$fix TASK-123` | `/fix TASK-123` |
| Refactorer | `$refactor ComponentName` | `/refactor ComponentName` |
| Tester | `$test TASK-123` | `/test TASK-123` |
| Reviewer | `$review CHANGE-123` | `/review CHANGE-123` |
| Documenter | `$document TASK-123` | `/document TASK-123` |

Le texte libre est équivalent :

```text
Implémente TASK-123.
Corrige le bug où une transaction FAILED reste PENDING.
Refactore PaymentOrchestrator sans modifier son comportement.
Analyse la continuité d’apprentissage sans modifier le code.
```

L’adapter conserve la demande complète. Le Runtime détermine l’intention, crée
une Task locale ou résout la référence externe, puis sélectionne le workflow.

Pour un Skill natif, l’adapter transmet aussi l’intention et le workflow attendus
avec `--intent` et `--expect-workflow`. Avant toute analyse détaillée ou
modification, la session doit afficher un reçu Runtime réel contenant au moins :

```yaml
runtimeReceipt: created
execution: <execution-id>
intent: implement
workflow:
  id: implement-task
nextPhase: understand
taskLog: <workspace>/.ai/runtime/tasks/<task-id>/events.jsonl
```

`Successfully loaded skill` signifie uniquement que l’agent a chargé ses
instructions. Une phrase comme `Task normalized` sans reçu ni Execution ne
constitue pas une exécution Factory et doit provoquer un arrêt fermé.

Le journal peut être consulté pendant ou après l’exécution :

```bash
aief task log <task-id> \
  --project "$PROJECT_ROOT" \
  --factory "$GAD_AI_FACTORY_HOME"
```

Il permet de vérifier la trajectoire réellement persistée : intention,
workflow, phases, artifacts, décisions de policy, gates, workspace et
validations. Voir [`26-task-execution-log.md`](26-task-execution-log.md).

## 3. Ce qui se passe automatiquement

```text
Demande utilisateur
  ↓
Skill/intent de l’agent
  ↓
aief run (appel interne)
  ↓
Task + Execution persistées dans .ai/runtime
  ↓
execution next
  ↓
Core Skill + contexte d’ingénierie effectif
  ↓
Claude/Codex réalise le travail agentique
  ↓
artifact structuré + complete-phase
  ↓
phase suivante, gate ou fin
```

L’adapter ne choisit ni l’ordre des phases, ni l’autonomie, ni les commandes de
validation. Ces décisions appartiennent au Runtime commun.

## 4. Premier scénario recommandé : analyse seule

Dans Codex :

```text
$analyze Analyse l’architecture actuelle, vérifie les documents contre le code
et les tests, et ne modifie aucun fichier.
```

Dans Claude Code :

```text
/analyze Analyse l’architecture actuelle, vérifie les documents contre le code
et les tests, et ne modifie aucun fichier.
```

Ou, dans les deux agents :

```text
Analyse l’architecture actuelle, vérifie les documents contre le code et les
tests, et ne modifie aucun fichier.
```

Résultat attendu : une Task locale, une Execution `analyze-task`, des artifacts
structurés et aucune modification du code.

## 5. Deuxième scénario : petite modification locale

Après validation du scénario précédent :

```text
Ajoute les tests manquants pour <comportement précis>. Ne modifie pas le
comportement fonctionnel et arrête-toi avant tout commit.
```

Avec une autonomie maximale `L2`, l’agent peut analyser, modifier localement et
tester. Il ne peut pas pousser, ouvrir une MR ou créer une tâche externe.

## 6. Scénario sans MCP

Configurer explicitement le projet pour que la traçabilité Factory locale soit
le système de référence :

```yaml
integrations: {}
taskTracking:
  mode: local
```

Sans `task-provider`, ne donnez pas une référence qui nécessite une récupération
externe. Fournissez la demande complète ou une référence documentaire locale :

```text
Analyse les priorités décrites dans docs/AUDIT.md et vérifie leur état réel dans
le code. Ne modifie aucun fichier.
```

La Factory crée une Task locale. Même si le risque ou le nombre de repositories
rend le niveau de tracking `required`, la Task, l'Execution, les artifacts et le
journal `.ai/runtime/tasks/<task-id>/events.jsonl` satisfont cette exigence.
Aucun provider n'est résolu.

Avec `taskTracking.mode: external`, le comportement reste strict : une exigence
`required` bloque tant qu'une référence externe n'est pas liée. Le Runtime ne
bascule jamais automatiquement d'un mode vers l'autre.

## 7. Gates et questions utilisateur

Lorsque le Runtime exige une validation humaine, l’agent doit :

1. arrêter la progression de l’Execution ;
2. présenter la phase, l’action et le risque concernés ;
3. demander une décision précise ;
4. enregistrer l’approbation ou le refus ;
5. reprendre la même Execution, sans en créer une nouvelle.

Répondre en texte naturel suffit. Le développeur n’appelle pas
`aief execution approve` lui-même : l’adapter traduit sa décision.

## 8. Reprise par un autre agent

Si Claude Code est interrompu :

```bash
cd "<PROJECT_ROOT>"
codex
```

Puis :

```text
Reprends la tâche active en utilisant l’état Factory persistant.
```

Codex doit lire `.ai/runtime/`, vérifier l’état Git et reprendre la prochaine
phase déclarée par le Runtime. La conversation Claude n’est jamais une source de
vérité nécessaire à cette reprise.

## 9. Reprendre après une mise à niveau de la Factory

Une session qui a déjà chargé un Skill peut conserver ses anciennes
instructions. Après une mise à niveau du Runtime, du protocole ou d’un Skill :

1. arrêter l’action en cours avant toute nouvelle modification ;
2. quitter complètement Claude Code ou Codex ;
3. vérifier que le CLI expose les nouvelles options ;
4. vérifier que le Skill installé pointe vers la Factory attendue ;
5. relancer l’agent depuis la racine du workspace ;
6. invoquer à nouveau l’intention et contrôler le reçu Runtime.

```bash
aief run --help | grep -- '--expect-workflow'
aief task --help | grep log

test -f "$HOME/.claude/skills/implement/SKILL.md"
# ou : test -f "$HOME/.agents/skills/implement/SKILL.md"

cd "$PROJECT_ROOT"
claude
# ou : codex
```

Dans la nouvelle session, utiliser la syntaxe propre à l'agent :

```text
Codex      $implement Feature 1.1 — Fixer les trois contrats cassés
Claude     /implement Feature 1.1 — Fixer les trois contrats cassés
```

Le reçu doit contenir `execution`, `intent`, `workflow`, `nextPhase` et
`taskLog`. Si l’agent affiche seulement `Successfully loaded skill` ou affirme
que la Task est normalisée sans reçu, arrêter l’exécution.

Les commandes affichées dans les demandes de permission doivent contenir des
chemins absolus littéraux. Cette commande provoque volontairement un prompt car
Claude ne peut pas l’analyser statiquement :

```bash
aief execution complete-phase <id> \
  --project "$(pwd)" \
  --factory "${GAD_AI_FACTORY_HOME}"
```

La forme correcte est :

```bash
aief execution complete-phase <id> \
  --output "/absolute/project/.ai/runtime/executions/<id>/phase-output.yaml" \
  --project "/absolute/project" \
  --factory "/absolute/factory" \
  --json
```

Le parcours Codex détaillé, notamment le diagnostic de `$implement`, est décrit
dans [`27-codex-usage.md`](27-codex-usage.md).

Si Claude propose encore `$(pwd)` ou `${...}`, refuser la permission, arrêter
la session et la relancer après mise à niveau du Skill.

Si l’agent indique que la Factory n’est pas configurée, vérifier dans sa propre
session :

```bash
printenv GAD_AI_FACTORY_HOME
test -f "$GAD_AI_FACTORY_HOME/factory.yaml"
```

La présence de l’export dans `.zshrc` ne prouve pas qu’un processus lancé depuis
un IDE, une application graphique ou une ancienne session l’a hérité. Quitter
l’agent, recharger l’environnement dans le terminal puis relancer depuis ce
même terminal. Voir la section « Rendre la Factory visible au processus agent »
du [guide d’installation](22-project-installation-guide.md).

### Workspace déjà modifié par l’ancienne session

Ne pas supprimer, stasher ou incorporer automatiquement les fichiers concernés.
Les conserver comme modifications locales non attribuées, relancer la nouvelle
Execution et laisser Workspace Safety les détecter. Le Runtime doit se bloquer
avant `implement-change` et demander une décision explicite. Une confirmation
native Claude/Codex ne vaut pas approbation d’un gate Factory.

## 10. Quand utiliser directement `aief`

Uniquement pour administrer ou diagnostiquer :

```bash
aief validate . --factory "$GAD_AI_FACTORY_HOME"
aief doctor .
aief integrations doctor . --factory "$GAD_AI_FACTORY_HOME"
aief execution inspect <execution-id> --project . --factory "$GAD_AI_FACTORY_HOME"
```

`aief run` reste une interface bas niveau destinée aux adapters, aux tests
d’intégration et au diagnostic du Runtime.

## 11. Vérification rapide

Avant la première tâche mutante :

- [ ] l’agent a été lancé depuis la racine contenant `.ai/project.yaml` ;
- [ ] le skill adapter est installé ;
- [ ] `GAD_AI_FACTORY_HOME` résout la version épinglée ;
- [ ] la demande est passée automatiquement au Runtime ;
- [ ] une Execution apparaît dans `.ai/runtime/` ;
- [ ] le reçu contient `taskLog` et le journal commence par `task.normalized` ;
- [ ] l’agent respecte les gates et le niveau d’autonomie ;
- [ ] les changements préexistants du développeur restent intacts.
