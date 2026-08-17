# 26 — Journal d’exécution par Task

Chaque demande normalisée possède un journal append-only local :

```text
.ai/runtime/tasks/<task-id>/events.jsonl
```

Le journal décrit le parcours observable de la demande indépendamment de la
conversation Claude/Codex. Le contrat complet de l'enveloppe d'événement, la
liste des types et les garanties de sécurité (redaction, opt-in) sont décrits
dans [`32-runtime-observability.md`](32-runtime-observability.md) ; ce document
se concentre sur la consultation opérationnelle du journal d'une Task.

Chaque événement porte un `event.id`/`event.type`/`event.timestamp`, l'id de
`project`, de `task`, et de `execution` quand une Execution existe déjà. Les
décisions sont tracées par leur résultat, leurs raisons déclarées et
l'artifact produit, dans `payload`. Le journal ne contient ni raisonnement
privé, ni secret, ni transcription complète de conversation.

Exemple :

```json
{"event":{"id":"event-abc123","type":"policy.reclassified","timestamp":"2026-09-02T10:00:00Z"},"factory":{"version":"1.15.0"},"project":{"id":"emmany"},"task":{"id":"EGW-142"},"execution":{"id":"exec-142"},"payload":{"status":"decided","risk":"high","authorizedAutonomy":"L2","requiredGates":["before-implementation"]}}
```

Consultation :

```bash
aief task log <task-id> --project . --factory "$GAD_AI_FACTORY_HOME"
aief task log <task-id> --project . --factory "$GAD_AI_FACTORY_HOME" --json
```

Le dossier `.ai/runtime/` reste gitignoré. Pour une trace durable, le workflow
`record-traceability` publie uniquement le résumé validé vers le provider
configuré. Le journal local facilite diagnostic, reprise et handoff, mais ne
remplace pas GitLab, GitHub ou Jira comme système de delivery.

## Vérifier une exécution `/implement`

Une exécution conforme doit commencer au minimum par :

```text
request.created
intent.resolved
task.normalized
workflow.started
phase.started (understand)
```

Puis chaque phase doit produire une trajectoire observable :

```text
phase.started
phase.completed
```

Avant la première modification source, le journal doit montrer les phases
préalables terminées et la préparation de `implement-change`. Si un fichier est
modifié alors que le dernier événement est `workflow.started`, ou si le
workflow est `analyze-task`, la modification n’est pas attribuable à une
Execution Factory conforme.

## Après une mise à niveau

Les journaux ne sont pas reconstruits rétroactivement. Une Task créée avant
l’introduction de cette fonctionnalité peut donc retourner une liste vide. Les
nouvelles Tasks sont journalisées dès `task.normalized`.

Après modification d’un Skill ou du Runtime, quitter complètement la session
agent et en ouvrir une nouvelle. Vérifier ensuite le `runtimeReceipt` et le
champ `taskLog` avant de laisser l’agent poursuivre. La procédure détaillée se
trouve dans [`23-first-steps.md`](23-first-steps.md).

## Résolution des Core Skills

`aief execution next` retourne un contrat résolu :

```yaml
skillContract:
  id: understand-task
  invocation: core-contract
  manifest: <factory>/core/skills/understand-task/skill.yaml
  instructions: <factory>/core/skills/understand-task/SKILL.md
  outputSchema: <factory>/core/skills/understand-task/output.schema.json
```

Claude/Codex lit ces fichiers puis produit l’artifact attendu. Il ne doit pas
appeler un hypothétique `Skill(understand)` : seuls les points d’entrée publics
`implement`, `fix`, `review`, etc. sont des Skills natifs de l’adapter.

Pour `analyze-impact`, l'événement `phase.completed` ne doit apparaître qu'après
validation de `details.repositories`. Cette liste est automatiquement propagée
vers la Task et l'Execution. Une correction manuelle de `task.yaml`,
`execution.yaml` ou d'un artifact terminé invalide la traçabilité et doit être
refusée.

Toutes les commandes suivantes conservent explicitement `--project` et
`--factory`. Une erreur `Factory manifest not found` provoque un arrêt fermé ;
elle ne doit jamais être contournée avec un lien ou une copie de `factory.yaml`
dans le workspace projet.
