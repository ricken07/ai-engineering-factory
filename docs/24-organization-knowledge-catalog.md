# 24 — Ajouter la connaissance de l’organisation

## Objectif

La connaissance organisationnelle doit être écrite une fois, versionnée,
gouvernée par des contrats Factory et composée avec les conventions propres à
chaque projet et repository.

```text
Repository documentaire organisationnel
  → catalogue épinglé dans Factory/organization/catalogs
  → manifestes Practice
  → Profiles et activations explicites
  → Project / Repository / Task specializations
  → EffectiveEngineeringContext
  → Core Skill
  → Claude Code ou Codex
```

Les fichiers sous `organization/catalogs/` et `organization/practices/` sont
des extensions optionnelles. Ils ne constituent pas une organisation implicite
de la Factory. Pour créer un catalogue propre à une organisation, partir du
modèle [`templates/organization/catalog.yaml`](../templates/organization/catalog.yaml)
et du manifeste `Practice` présenté plus bas, puis le sélectionner
explicitement dans le projet.

Le Core reste agnostique : il définit seulement le contrat `Practice` et les
catégories de contexte consommées par les Skills.

Ce catalogue de connaissances ne doit pas être confondu avec le catalogue des
intégrations. Les conventions et pratiques vivent sous `organization/`; les
providers GitLab, GitHub, Jira ou Confluence vivent sous `integrations/`.
L'organisation gouverne les deux, mais un projet ne fait qu'en sélectionner les
éléments autorisés. Le modèle MCP complet est défini dans
[`13-agent-adapters-and-mcp.md`](13-agent-adapters-and-mcp.md).

## Sources et responsabilités

| Niveau | Responsabilité |
| --- | --- |
| Dépôt guidelines | Contenu humain de référence et historique éditorial |
| `organization/catalogs/` | Révision exacte de la source installée avec la Factory |
| Manifeste `Practice` | Version, catégorie, enforcement, applicabilité et override |
| `OrganizationCatalog` | Liste des Practices, héritage et bindings par Profile |
| Profile | Détection et connaissance technique, sans préférence d’organisation |
| Projet | Sélection explicite des catalogues et conventions propres au projet |
| Repository | Activation liée à son rôle et spécialisation locale |
| Task | Contrainte temporaire gouvernée, jamais mémoire globale |

## Pourquoi utiliser un sous-module

Un chemin absolu tel que `/Users/.../gd-extensions/guidelines` varie selon le
poste, échappe au catalogue sécurisé et rend le contexte non reproductible. Une
copie manuelle diverge rapidement de la source.

Le sous-module conserve :

- une source Git autonome ;
- un commit exact dans chaque version de Factory ;
- une installation reproductible ;
- des mises à jour explicites et reviewables ;
- un fingerprint de contenu stable dans l’EffectiveEngineeringContext.

Installation :

```bash
git clone --recurse-submodules <FACTORY_REPOSITORY_URL> <FACTORY_HOME>
```

Clone existant :

```bash
git submodule update --init --recursive
```

## Déclarer un catalogue configurable

Une Factory peut embarquer plusieurs catalogues sans en imposer un globalement :

```yaml
apiVersion: factory.gaddigital.io/v1alpha1
kind: OrganizationCatalog
metadata:
  id: example-organization
  name: Example Organization Engineering Catalog
  version: 1.0.0
extends: [factory-default@1.0.0]
practiceRefs:
  - example-java-guidelines@1.0.0
  - example-app-architecture@1.0.0
profileBindings:
  java: [example-java-guidelines@1.0.0]
```

Le catalogue `factory-default` constitue un socle optionnel. Une organisation
peut l’étendre, sélectionner plusieurs catalogues compatibles ou fournir un
catalogue entièrement indépendant.

Le projet choisit explicitement :

```yaml
engineering:
  inheritOrganization: true
  organizationCatalogs:
    - example-organization@1.0.0
```

Le Runtime résout les parents, vérifie les versions, refuse les cycles et inclut
la provenance des catalogues dans le fingerprint du contexte effectif.

## Transformer un document en Practice

Un Markdown seul n’est pas chargé par le Runtime. Il doit être exposé par un
manifeste YAML situé sous `organization/` :

```yaml
apiVersion: factory.gaddigital.io/v1alpha1
kind: Practice
metadata:
  id: organization-api-guidelines
  name: Organization API Guidelines
  version: 1.0.0
category: convention
enforcement: optional
appliesTo:
  profiles: [java, spring]
  skills: [analyze-impact, create-plan, implement-change, review-change]
document:
  path: ../../catalogs/guidelines/api-guidelines.md
inheritance:
  strategy: merge
override:
  allowed: false
tags: [java, spring, api]
```

Le chemin du document est relatif au manifeste et doit rester à l’intérieur de
`organization/`. Le Runtime rejette les documents absents ou les chemins qui
échappent à ce catalogue.

## Choisir l’enforcement

### `mandatory`

Règle applicable automatiquement et non surchargeable. À réserver aux
invariants réellement universels : secrets, sécurité, obligations réglementaires
ou baseline qualité organisationnelle.

```yaml
enforcement: mandatory
override: {allowed: false}
```

### `default`

Pratique héritée lorsqu’un Profile la référence. Elle peut être spécialisée
uniquement si `override.allowed` vaut `true`.

```yaml
enforcement: default
override: {allowed: true}
```

### `optional`

Pratique disponible mais activée explicitement. C’est le bon choix pour une
architecture ou un rôle qui ne concerne pas tous les repositories d’une stack :
API contractuelle, APP en couches, architecture hexagonale ou event-driven.

```yaml
enforcement: optional
override: {allowed: false}
```

## Binding par Profile sans coupler les Profiles

Les Profiles restent indépendants des organisations. C’est le catalogue qui
associe une pratique générale à une technologie :

```yaml
# organization/catalogs/example-organization.yaml
profileBindings:
  java:
    - example-java-development-guidelines@1.0.0
  spring:
    - example-spring-guidelines@1.0.0
```

Une architecture propre aux repositories `*-api` ou `*-app` ne doit pas être
activée par le seul Profile Spring : les deux rôles utilisent la même stack.
Elle doit rester `optional` et être sélectionnée au niveau repository.

## Activation par projet et repository

```yaml
engineering:
  inheritOrganization: true
  organizationCatalogs: [example-organization@1.0.0]

repositories:
  - id: product-api
    profiles: [java, spring, maven]
    engineering:
      practices:
        organization-api-guidelines@1.0.0:
          mode: enable

  - id: product-app
    profiles: [java, spring, maven]
    engineering:
      practices:
        organization-app-architecture@1.0.0:
          mode: enable
```

Le suffixe `@version` fait échouer explicitement la résolution si la Factory
installée expose une autre version de la pratique.

### Organisation uniquement au niveau d’un projet

Un projet qui ne dépend d’aucun catalogue organisationnel peut désactiver cette
couche sans désactiver ses propres conventions :

```yaml
engineering:
  inheritOrganization: true
  organizationCatalogs: []
  practices:
    product-architecture:
      mode: enable
      category: architecture
      ref: .ai/context/architecture.md
```

Dans ce cas, seules les pratiques locales explicites et les documents de
contexte projet sont transmis aux Skills. Aucun catalogue organisationnel
n’est chargé implicitement.

## Ajouter une convention propre au projet

Les conventions locales restent dans `.ai/context/` et complètent le catalogue :

```yaml
repositories:
  - id: product-app
    engineering:
      practices:
        product-app-conventions:
          mode: enable
          category: convention
          ref: .ai/context/repositories/product-app-conventions.md
```

Une spécialisation autorisée d’une pratique existante utilise `override` :

```yaml
engineering:
  practices:
    organization-java-development-guidelines@1.0.0:
      mode: override
      ref: .ai/context/java-development-specialization.md
```

Avec `inheritance.strategy: merge`, le contenu organisationnel est conservé et
la spécialisation locale est ajoutée. Avec `replace`, seul le document local est
fourni. Une pratique `mandatory` ou protégée reste non surchargeable.

## Chargement progressif

Chaque Core Skill demande uniquement les catégories utiles :

```yaml
engineeringContext:
  requires: [architecture, convention, security, testing]
```

Le Runtime filtre ensuite par Profile, Skill, projet et repository. Un guide
Java n’est pas envoyé à Flutter ; une pratique de review n’est pas chargée
pendant `understand-task`.

## Mise à jour du catalogue

1. modifier et reviewer le dépôt documentaire source ;
2. idéalement créer un tag de guidelines ;
3. mettre à jour le sous-module sur une branche Factory ;
4. incrémenter la version des Practices dont le contenu ou la gouvernance change ;
5. mettre à jour les références `@version` des projets concernés ;
6. exécuter `aief validate` et les tests de contexte ;
7. publier une nouvelle version de Factory ;
8. mettre à niveau les projets explicitement.

```bash
git -C organization/catalogs/guidelines fetch --tags
git -C organization/catalogs/guidelines checkout <TAG_OR_COMMIT>
git add organization/catalogs/guidelines
aief validate .
pytest -q
```

Ne suivez jamais silencieusement la branche principale du dépôt documentaire
depuis une installation déjà publiée.

## Contrôles avant publication

- [ ] identifiant de Practice unique et stable ;
- [ ] identifiant et version de catalogue stables ;
- [ ] héritage de catalogue sans cycle ;
- [ ] version cohérente avec le contenu ;
- [ ] catégorie consommée par les Skills attendus ;
- [ ] profiles et skills d’applicabilité minimaux ;
- [ ] enforcement justifié ;
- [ ] override explicitement autorisé ou interdit ;
- [ ] document résolu sous `organization/` ;
- [ ] sous-module épinglé sur un commit connu ;
- [ ] activation repository testée ;
- [ ] contexte effectif inspecté et fingerprinté ;
- [ ] aucune règle projet dupliquée dans le catalogue organisationnel.
