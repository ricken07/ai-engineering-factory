# 23 — Premiers pas dans un projet Factory

Ce guide commence après l’installation décrite dans
[`22-project-installation-guide.md`](22-project-installation-guide.md).

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

Sans `task-provider`, ne donnez pas une référence qui nécessite une récupération
externe. Fournissez la demande complète ou une référence documentaire locale :

```text
Analyse les priorités décrites dans docs/AUDIT.md et vérifie leur état réel dans
le code. Ne modifie aucun fichier.
```

La Factory crée une Task locale. Si une policy exige plus tard une traçabilité
externe, l’Execution se bloque explicitement au lieu de simuler un provider.

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

## 9. Quand utiliser directement `aief`

Uniquement pour administrer ou diagnostiquer :

```bash
aief validate . --factory "$GAD_AI_FACTORY_HOME"
aief doctor .
aief integrations doctor . --factory "$GAD_AI_FACTORY_HOME"
aief execution inspect <execution-id> --project . --factory "$GAD_AI_FACTORY_HOME"
```

`aief run` reste une interface bas niveau destinée aux adapters, aux tests
d’intégration et au diagnostic du Runtime.

## 10. Vérification rapide

Avant la première tâche mutante :

- [ ] l’agent a été lancé depuis la racine contenant `.ai/project.yaml` ;
- [ ] le skill adapter est installé ;
- [ ] `GAD_AI_FACTORY_HOME` résout la version épinglée ;
- [ ] la demande est passée automatiquement au Runtime ;
- [ ] une Execution apparaît dans `.ai/runtime/` ;
- [ ] l’agent respecte les gates et le niveau d’autonomie ;
- [ ] les changements préexistants du développeur restent intacts.

