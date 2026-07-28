# 25 — Permissions projet pour Claude Code et Codex

Les fichiers de permissions natifs rendent l’exécution quotidienne de la
Factory fluide sans désactiver le contrôle humain. Ils sont livrés par le
template projet :

```text
.claude/settings.json
.codex/config.toml
.codex/rules/factory.rules
```

Ils ne remplacent jamais les policies de la Factory. Une action n’est possible
que si les trois couches l’autorisent :

```text
PolicyDecision Factory
        ∩
permission native Claude/Codex
        ∩
sandbox et droits du système
        ↓
action effectivement autorisée
```

Une permission native peut donc empêcher une action autorisée par la Factory,
mais elle ne doit jamais élargir l’autonomie calculée par la Factory.

## 1. Classification commune

| Classe | Exemples | Comportement |
| --- | --- | --- |
| Autorisé | lecture, `aief validate`, inspection d’Execution, état Git | sans confirmation répétitive |
| Confirmation | gate, création de ticket, commit/push, mutation de branche/worktree, validation exécutée hors sandbox | demander à l’humain |
| Interdit | force-push, hard reset, git clean destructif, lecture de secrets | bloquer |

Le modèle partagé est volontairement conservateur. Les permissions d’un
provider MCP se configurent séparément et restent soumises aux mêmes policies.

La baseline autorise `Bash(aief *)` afin que les opérations Runtime ordinaires
ne redemandent pas une permission à chaque phase. Les règles `ask` spécifiques
aux approbations, écritures externes, synchronisations et mutations Git sont
évaluées avant cette règle générale et restent interactives. Les interdictions
destructrices restent prioritaires.

## 2. Claude Code

Claude Code charge la configuration partagée depuis
`.claude/settings.json`. Le template utilise `acceptEdits` pour éviter une
confirmation à chaque modification locale, puis encadre les commandes Bash
avec `allow`, `ask` et `deny`.

Le fichier local `.claude/settings.local.json` est ignoré par Git. Il sert aux
ajustements propres au poste, jamais à contourner une règle organisationnelle.
Il peut également fournir `GAD_AI_FACTORY_HOME` à Claude lorsque le client est
lancé depuis un IDE ou une application qui n’hérite pas du shell :

```json
{
  "env": {
    "GAD_AI_FACTORY_HOME": "<ABSOLUTE_FACTORY_INSTALLATION>"
  }
}
```

Fusionner cette clé avec les permissions locales existantes et ne jamais
commiter ce fichier.

Vérification depuis Claude Code :

```text
/permissions
```

Contrôler que les règles projet sont chargées, puis commencer par `/analyze`.
Ne pas utiliser `bypassPermissions` ni `--dangerously-skip-permissions` pour le
fonctionnement normal de la Factory.

Les commandes Factory doivent être simples et littérales :

```bash
aief execution next 20260816T120000Z-example \
  --project "/absolute/project" \
  --factory "/absolute/factory"
```

Éviter dans la commande soumise à Bash :

```bash
$(pwd)
${GAD_AI_FACTORY_HOME}
${GAD_AI_FACTORY_HOME:-.}
cd ... && aief ...
```

L’adapter résout d’abord les chemins, puis réutilise leurs valeurs absolues
littérales. Les substitutions et commandes composées sont plus difficiles à
valider par les permissions natives et provoquent des prompts supplémentaires.

## 3. Codex

Codex charge `.codex/config.toml` et `.codex/rules/` uniquement après que le
repository a été déclaré de confiance. Le template impose :

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false
```

Le code et `.ai/runtime/` restent modifiables dans le workspace. Une commande
qui exige un accès hors sandbox déclenche les règles de
`.codex/rules/factory.rules`. Les règles `forbidden` l’emportent sur `prompt`,
qui l’emporte sur `allow`.

Tester les règles avant adoption :

```bash
codex execpolicy check --pretty \
  --rules .codex/rules/factory.rules \
  -- git reset --hard HEAD

codex execpolicy check --pretty \
  --rules .codex/rules/factory.rules \
  -- aief execution approve exec-example
```

Le premier résultat doit être `forbidden`, le second `prompt`.

## 4. Ajouter les commandes propres au projet

Le template générique ne présume aucune stack. Après activation des Profiles,
le projet peut ajouter uniquement les validations réellement nécessaires.

Claude Code, exemple Maven :

```json
"Bash(./mvnw verify *)"
```

Claude Code, exemple Flutter :

```json
"Bash(flutter analyze *)",
"Bash(flutter test *)"
```

Codex, exemple Maven à ajouter dans un fichier
`.codex/rules/project-validations.rules` :

```python
prefix_rule(
    pattern = ["./mvnw", "verify"],
    decision = "allow",
    justification = "Validation Maven déclarée par le Profile du repository",
    match = ["./mvnw verify"],
)
```

Avant d’autoriser une commande :

1. vérifier qu’elle provient d’un Profile ou d’une convention projet validée ;
2. utiliser un préfixe précis, jamais `Bash` ou `npm` globalement ;
3. ne pas autoriser les options destructrices ou de publication ;
4. ajouter un exemple de test dans la règle Codex ;
5. faire reviewer le changement comme une modification de sécurité.

## 5. Actions qui doivent rester interactives

Même avec une autonomie projet L3 ou L4, les fichiers natifs partagés ne
doivent pas auto-approuver :

- un gate humain Factory ;
- la création ou liaison d’une tâche externe ;
- un commit, push, merge ou rebase ;
- une préparation ou un rollback de workspace ;
- l’ajout d’un MCP ou l’élévation de ses permissions ;
- toute commande demandant un accès réseau ou hors workspace non documenté.

La policy peut refuser l’action après la confirmation native. L’inverse n’est
pas vrai : confirmer une fenêtre Claude/Codex ne valide pas un gate Factory.

## Identité Git et messages de commit

La Factory ne signe pas les commits au nom de l’agent. Lorsqu’un commit est
autorisé, Claude ou Codex peut préparer le message selon les conventions de
l’organisation, mais Git doit utiliser le profil déjà configuré par le
développeur :

```bash
git config user.name
git config user.email
git config --get commit.gpgsign
git config --get user.signingkey
```

L’agent ne doit pas utiliser `--author`, `--reset-author`, `GIT_AUTHOR_*`,
`GIT_COMMITTER_*`, ni remplacer la clé de signature. Il ne doit pas ajouter
automatiquement une signature ou une mention `Co-authored-by` représentant
l’agent. L’identité et l’état de signature sont enregistrés avant le commit ;
une identité absente ou différente du profil développeur bloque la gate
`before-commit`.

## 6. Installation et contrôle

`aief init` copie les fichiers avec le reste du template. Pour un projet déjà
configuré, les copier et les reviewer sans écraser des réglages existants :

```bash
mkdir -p .claude .codex/rules
cp "<FACTORY_HOME>/templates/project/.claude/settings.json" .claude/settings.json
cp "<FACTORY_HOME>/templates/project/.codex/config.toml" .codex/config.toml
cp "<FACTORY_HOME>/templates/project/.codex/rules/factory.rules" .codex/rules/factory.rules
```

Puis :

```bash
aief validate . --factory "<FACTORY_HOME>"
git diff -- .claude .codex .gitignore
```

Redémarrer Claude Code ou Codex : les deux clients découvrent leur
configuration projet au démarrage. Commencer par une analyse non mutante, puis
une petite modification locale avec autonomie maximale L2.

## 7. Sources natives

- Claude Code — settings et scopes : <https://code.claude.com/docs/en/settings>
- Codex — configuration : <https://developers.openai.com/codex/config-reference>
- Codex — règles de commandes : <https://developers.openai.com/codex/rules>
