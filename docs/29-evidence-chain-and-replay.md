# 29 — Chaîne de preuves et replay des validations

## Objectif

Une auto-évaluation de l’agent ne suffit pas pour déclarer une modification
conforme. La Factory exige une chaîne de preuves structurée, persistée et
rejouable avant la soumission.

```text
Besoin
  → critères d'acceptation
  → plan
  → implémentation
  → validations
  → matrice de preuves
  → review indépendante
  → soumission autorisée
```

## Critères d’acceptation

Le plan doit exposer les critères dans `planning.yaml` :

```yaml
details:
  acceptanceCriteria:
    - id: AC-001
      statement: "Le contrat API reste compatible."
    - id: AC-002
      statement: "La lecture respecte l'utilisateur authentifié."
```

Chaque critère doit être couvert dans `validation.yaml` par un élément de
`details.evidenceMatrix` :

```yaml
details:
  evidenceMatrix:
    - id: AC-001
      status: verified
      evidence: [EV-001]
```

Un critère sans preuve, ou avec un statut différent de `verified`, bloque la
soumission.

## Preuves de validation

`validate-change` conserve notamment :

- `details.validationPlan` : commandes exactes et repositories concernés ;
- `details.results` : code retour, sortie et erreur de chaque commande ;
- `details.commits` : commit Git testé par repository ;
- `details.evidenceMatrix` : couverture des critères.

Une validation réussie doit donc être rattachée au code réellement testé,
et non seulement à une affirmation de l’agent.

## Review indépendante

La review doit être produite indépendamment de l’implémentation. Elle doit
contenir :

```yaml
details:
  independent: true
  implementationSession: implementation-123
  reviewerSession: review-456
  decision: approved
  blockingFindings: []
```

Le Runtime refuse la soumission si les sessions sont identiques, si la review
n’est pas approuvée ou si des findings bloquants restent ouverts.

## Replay

Les validations peuvent être rejouées avec :

```bash
aief execution replay-validation <execution-id> \
  --project "<PROJECT_ROOT>" \
  --factory "<FACTORY_HOME>"
```

Le Runtime relit le plan enregistré, vérifie que chaque repository est
toujours sur le commit testé, puis réexécute les commandes sans modifier le
code. Le résultat est conservé dans :

```text
.ai/runtime/executions/<execution-id>/validation-replay.yaml
```

Si le repository a changé depuis la validation initiale, le replay échoue et
une nouvelle validation est nécessaire.

## Gate de soumission

`submit-change` exige les éléments suivants :

```text
planning.yaml présent
validation.yaml présent et réussi
matrice de preuves complète
review indépendante approuvée
aucun finding bloquant
gates de policy satisfaites
```

Cette vérification intervient avant tout commit, MR/PR ou merge. Le choix du
mode de livraison et les gates d’autorisation restent séparés de la preuve
technique.
