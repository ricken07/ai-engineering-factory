# Gad Digital — Guide de Développement d'API

> **Ce document est la spécification de référence** pour concevoir et implémenter les contrats d'API
> chez Gad Digital. Il s'adresse aux développeurs **et aux agents IA** qui génèrent du code.
> Toute API produite doit être conforme à ce guide.

| Propriété | Valeur |
|---|---|
| **Runtime** | Java 25 |
| **Framework** | Spring Boot 4.x |
| **Style architectural** | Actor Pattern + REST + Contrats immutables (Java records) |
| **Documentation API** | OpenAPI v3 (annotations Swagger `io.swagger.v3`) — API First |
| **Plugins communs** | `gd-backend-runtime` (JWT, filtres cross-cutting, gestion d'erreurs) · `gd-api-conformity` (validation de conformité) |

---

## 1. Convention de nommage des packages

### 1.1 Package racine du projet

Deux cas de figure existent selon que l'API est développée pour un **client** ou pour un **projet interne** Gad Digital.

| Type de projet | Format du package racine | Exemple |
|---|---|---|
| Projet **client** | `io.gaddigital.<code_client>.<code_projet>.api` | `io.gaddigital.kabs.okl.api` |
| Projet **Gad Digital** | `io.gaddigital.<code_projet>.api` | `io.gaddigital.emi.api` |

> **Règle :** le package racine se termine toujours par `.api`.
> Dans la suite de ce document, `<root>` désigne le package racine du projet
> (ex : `io.gaddigital.emi.api` ou `io.gaddigital.kabs.okl.api`).

### 1.2 Identifiants

| Élément | Casse | Exemples |
|---|---|---|
| `<code_client>` | lowercase | `kabs`, `bgfi` |
| `<code_projet>` | lowercase | `okl`, `emi`, `drs` |
| Packages | lowercase, point-séparé | `io.gaddigital.emi.api.game.operator` |

---

## 2. Organisation par domaine

Sous le package racine, le code est organisé **par domaine métier** :

```
<root>
├── game/            ← domaine "game"
├── configuration/   ← domaine "configuration"
├── billing/         ← domaine "billing"
├── student/         ← domaine "student"
└── …               ← autres domaines
```

Chaque domaine correspond à un **sous-package direct** de `<root>`.

Exemples :
- `io.gaddigital.emi.api.game`
- `io.gaddigital.emi.api.student`
- `io.gaddigital.kabs.okl.api.billing`

> **Note :** il n'y a **pas** de package `common` dans le projet API.
> Les composants transverses (ErrorResponse, erreurs communes, filtres) sont fournis par la lib
> `io.gd.lib:common`

---

## 3. Actor Pattern — Structure par acteur

### 3.1 Les trois acteurs

Chaque domaine expose ses API à travers un ou plusieurs **acteurs** fournis par la libs `io.gd.lib:common`. Trois acteurs sont définis :

| Acteur | Package | Rôle | Préfixe d'URL |
|---|---|---|---|
| **OPERATOR** | `operator` | APIs d'administration (back-office, ops) | `/operator/v1/<code_projet>/<domain>` |
| **TRUSTED** | `trusted` | APIs côté client vérifié (mobile, web auth) | `/trusted/v1/<code_projet>/<domain>` |
| **S2S** | `s2s` | APIs service-to-service (inter-microservices) | `/s2s/v1/<code_projet>/<domain>` |

> **Règle :** un domaine ne déclare que les acteurs dont il a besoin. Il n'est pas obligatoire de déclarer les trois si le besoin n'existe pas.

### 3.2 Package d'un acteur

```
<root>.<domain>.<actor>/
```

Exemples :
- `io.gaddigital.emi.api.game.operator`
- `io.gaddigital.emi.api.game.trusted`
- `io.gaddigital.emi.api.game.s2s`

### 3.3 Interface de contrat d'API (API Contract Interface)

À la **racine du package de l'acteur**, on place une **interface Java** qui constitue le contrat d'API du domaine pour cet acteur.

**Convention de nommage :** `<Actor><Domain>API`

| Acteur | Interface | Package |
|---|---|---|
| OPERATOR | `OperatorGameAPI` | `<root>.game.operator` |
| TRUSTED | `TrustedGameAPI` | `<root>.game.trusted` |
| S2S | `S2sGameAPI` | `<root>.game.s2s` |

Cette interface :
- est annotee `@RestController` (le controleur REST est porte par le contrat, pas par l'implementation),
- est annotee avec les annotations Swagger/OpenAPI (`@Tag`, `@Operation`, `@ApiResponse`, etc.),
- definit les signatures des endpoints du domaine pour cet acteur,
- **ne contient aucune logique** — elle est un contrat pur,
- **retourne** uniquement des `*DTO` ou des `*View`,
- **accepte en body** uniquement des `*Command`,
- **accepte en `@PathVariable` / `@RequestParam`** uniquement des types simples (`String`, `Long`, `UUID`, etc.).

---

## 4. Sous-packages d'un acteur

Chaque package acteur contient **obligatoirement** les sous-packages suivants (si le domaine en a besoin) :

```
<root>.<domain>.<actor>/
├── <Actor><Domain>API.java    ← interface de contrat (racine)
├── error/                     ← dictionnaire d'erreurs
│   └── Error<Domain>Dict.java
├── command/                   ← commandes (body des requêtes d'écriture)
│   ├── Create<X>Command.java
│   └── Update<X>Command.java
├── view/                      ← vues composées (réponses enrichies)
│   ├── <X>View.java
│   └── <Y>View.java
└── model/                     ← DTOs de transfert (réponses simples)
    ├── <X>DTO.java
    └── <Y>DTO.java
```

### 4.1 `error` — Dictionnaire d'erreurs

Contient un **enum** regroupant toutes les erreurs métier du domaine pour cet acteur.

**Convention de nommage :** `Error<Domain>Dict`

Exemples : `ErrorGameDict`, `ErrorConfigurationDict`, `ErrorBillingDict`

```java
package io.gaddigital.emi.api.game.operator.error;

public enum ErrorGameDict {
    GAME_NOT_FOUND,
    GAME_ALREADY_EXISTS,
    GAME_SESSION_EXPIRED,
    INVALID_GAME_STATE
}
```

### 4.2 `command` — Commandes (body des requêtes d'écriture)

Contient des **records Java** représentant les données envoyées en **body** d'une requête d'écriture (POST/PUT/PATCH). Les commandes incarnent l'intention d'action côté client.

**Convention de nommage :** `<Verbe><Entité>Command`

Exemples : `CreateGameCommand`, `UpdateConfigurationCommand`, `InitiatePaymentCommand`

```java
package io.gaddigital.emi.api.game.operator.command;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Commande de création d'un jeu.")
public record CreateGameCommand(

        @Schema(description = "Nom du jeu.", example = "Loto Express")
        String name,

        @Schema(description = "Type de jeu.", example = "LOTTERY")
        String type,

        @Schema(description = "Mise minimale en centimes.", example = "500")
        int minStakeCents
) {}
```

> **Règle :** chaque champ d'un record Command **doit** porter une annotation `@Schema` avec `description` et `example`.

### 4.3 `view` — Vues composées

Contient des **records Java** représentant des réponses **enrichies/composées**, typiquement assemblées à partir de plusieurs sources.

**Convention de nommage :** `<Entité>View`

Exemples : `GameSessionView`, `UserProfileView`, `InvoiceDetailView`

```java
package io.gaddigital.emi.api.game.trusted.view;

import io.swagger.v3.oas.annotations.media.Schema;
import java.time.Instant;

@Schema(description = "Vue détaillée d'une session de jeu.")
public record GameSessionView(

        @Schema(description = "Identifiant de la session.", example = "sess_abc123")
        String sessionId,

        @Schema(description = "Identifiant du jeu.", example = "game_001")
        String gameId,

        @Schema(description = "Statut de la session.", example = "ACTIVE")
        String status,

        @Schema(description = "Date de début de la session.", example = "2026-03-31T10:00:00Z")
        Instant startedAt,

        @Schema(description = "Mise totale en centimes.", example = "1500")
        int totalStakeCents
) {}
```

> **Règle :** chaque champ d'un record View **doit** porter une annotation `@Schema` avec `description` et `example`.

### 4.4 `model` — DTOs de transfert

Contient des **records Java** (DTOs) qui reflètent le domaine métier pour le transfert de données.

**Convention de nommage :** `<Entité>DTO`

Exemples : `GameDTO`, `ConfigurationDTO`, `AccountDTO`

```java
package io.gaddigital.emi.api.game.operator.model;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Représentation d'un jeu.")
public record GameDTO(

        @Schema(description = "Identifiant unique du jeu.", example = "game_001")
        String id,

        @Schema(description = "Nom du jeu.", example = "Loto Express")
        String name,

        @Schema(description = "Type de jeu.", example = "LOTTERY")
        String type,

        @Schema(description = "Statut du jeu.", example = "ACTIVE")
        String status
) {}
```

> **Règle :** chaque champ d'un record DTO **doit** porter une annotation `@Schema` avec `description` et `example`.

---

## 5. Convention de routage REST

### 5.1 Format d'URL

Toutes les URLs suivent le pattern :

```
/<actor>/<version>/<code_projet>/<domaine>[/<resource>[/{id}]]
```

| Segment | Description | Exemples |
|---|---|---|
| `<actor>` | Acteur de l'API | `operator`, `trusted`, `s2s` |
| `<version>` | Version de l'API | `v1` |
| `<code_projet>` | Code du projet | `emi`, `okl` |
| `<domaine>` | Domaine métier (au pluriel ou singulier selon la ressource) | `student`, `game`, `billing` |
| `<resource>` | Ressource REST | selon l'action |
| `{id}` | Identifiant de la ressource | path variable |

### 5.2 Exemples de routes REST

| Verbe HTTP | URL | Description | Body |
|---|---|---|---|
| `GET` | `/operator/v1/emi/student` | Lister les étudiants | — |
| `GET` | `/operator/v1/emi/student/{studentId}` | Obtenir un étudiant | — |
| `POST` | `/operator/v1/emi/student` | Créer un étudiant | `CreateStudentCommand` |
| `PUT` | `/operator/v1/emi/student/{studentId}` | Mettre à jour un étudiant | `UpdateStudentCommand` |
| `DELETE` | `/operator/v1/emi/student/{studentId}` | Supprimer un étudiant | — |
| `POST` | `/trusted/v1/emi/game/sessions` | Démarrer une session de jeu | `StartGameSessionCommand` |
| `GET` | `/trusted/v1/emi/game/sessions/{sessionId}` | Obtenir une session de jeu | — |
| `GET` | `/s2s/v1/okl/game` | Lister les jeux (service-to-service) | — |
| `POST` | `/operator/v1/emi/billing/invoices` | Créer une facture | `CreateInvoiceCommand` |

### 5.3 Règles de routage

- Les segments d'URL sont en **kebab-case** (si plusieurs mots).
- Les ressources REST décrivent **l'action ou la ressource ciblée** de manière explicite.
- Les verbes HTTP portent la sémantique de l'opération (GET = lecture, POST = création, PUT = mise à jour, DELETE = suppression).
- Les **body** de requête d'écriture (POST, PUT, PATCH) sont **toujours** des `*Command`.
- Les **réponses** sont **toujours** des `*DTO`, `*View`, ou des listes/pages de ceux-ci.
- Le `@RequestMapping` de l'interface de contrat porte le préfixe : `/<actor>/<version>/<code_projet>/<domaine>`.

---

## 6. Contrat d'interface — API First avec OpenAPI v3

### 6.1 Principes

- **Toute interface de contrat** (`<Actor><Domain>API`) doit être entièrement documentée via les annotations Swagger/OpenAPI v3.
- L'approche est **API First** : le contrat est défini avant l'implémentation.
- Le contrat d'interface fait office de **spécification vivante** : la documentation Swagger est générée à partir du code.

### 6.2 Annotations obligatoires

| Niveau | Annotations requises |
|---|---|
| **Interface** | `@RestController` + `@Tag(name = "…", description = "…")` |
| **Méthode** | `@Operation(summary = "…", description = "…")` |
| **Réponses** | `@ApiResponse(responseCode = "…", description = "…", content = @Content(schema = @Schema(implementation = …)))` |
| **Paramètres** | `@Parameter(description = "…", example = "…")` sur chaque `@PathVariable` et `@RequestParam` |
| **Body** | `@RequestBody` avec `@Content(schema = @Schema(implementation = …Command.class))` |
| **Records** | `@Schema(description = "…")` sur la classe et `@Schema(description = "…", example = "…")` sur chaque champ |

### 6.3 Règles de typage des paramètres

| Source du paramètre | Type autorisé |
|---|---|
| `@PathVariable` | Types simples : `String`, `Long`, `UUID`, `int`, etc. |
| `@RequestParam` | Types simples : `String`, `Long`, `UUID`, `int`, `boolean`, `Instant`, etc. |
| `@RequestBody` | **Uniquement** des records `*Command` |

| Type de retour | Classes autorisées |
|---|---|
| Réponse standard | `*DTO` ou `*View` (ou listes/pages de ceux-ci) |
| Réponse d'erreur | `ErrorResponse` (fourni par `gd-backend-runtime`) |

### 6.4 Exemple complet d'interface de contrat

```java
package io.gaddigital.emi.api.student.operator;

import io.gaddigital.emi.api.student.operator.command.CreateStudentCommand;
import io.gaddigital.emi.api.student.operator.command.UpdateStudentCommand;
import io.gaddigital.emi.api.student.operator.model.StudentDTO;
import io.gaddigital.emi.api.student.operator.view.StudentDetailView;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.tags.Tag;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@Tag(name = "Operator — Student", description = "APIs d'administration des étudiants.")
@RequestMapping("/operator/v1/emi/student")
public interface OperatorStudentAPI {

    @Operation(summary = "Lister les étudiants",
               description = "Retourne la liste de tous les étudiants.")
    @ApiResponse(responseCode = "200", description = "Liste des étudiants",
                 content = @Content(schema = @Schema(implementation = StudentDTO.class)))
    @GetMapping
    ResponseEntity<List<StudentDTO>> listStudents();

    @Operation(summary = "Obtenir un étudiant",
               description = "Retourne le détail d'un étudiant par son identifiant.")
    @ApiResponse(responseCode = "200", description = "Détail de l'étudiant",
                 content = @Content(schema = @Schema(implementation = StudentDetailView.class)))
    @ApiResponse(responseCode = "404", description = "Étudiant non trouvé")
    @GetMapping("/{studentId}")
    ResponseEntity<StudentDetailView> getStudent(
            @Parameter(description = "Identifiant de l'étudiant.", example = "stu_001")
            @PathVariable String studentId
    );

    @Operation(summary = "Créer un étudiant",
               description = "Inscrit un nouvel étudiant dans le système.")
    @ApiResponse(responseCode = "201", description = "Étudiant créé",
                 content = @Content(schema = @Schema(implementation = StudentDTO.class)))
    @ApiResponse(responseCode = "409", description = "Étudiant déjà existant")
    @PostMapping
    ResponseEntity<StudentDTO> createStudent(
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "Données de création de l'étudiant.",
                    content = @Content(schema = @Schema(implementation = CreateStudentCommand.class)))
            @RequestBody CreateStudentCommand command
    );

    @Operation(summary = "Mettre à jour un étudiant",
               description = "Met à jour les informations d'un étudiant existant.")
    @ApiResponse(responseCode = "200", description = "Étudiant mis à jour",
                 content = @Content(schema = @Schema(implementation = StudentDTO.class)))
    @ApiResponse(responseCode = "404", description = "Étudiant non trouvé")
    @PutMapping("/{studentId}")
    ResponseEntity<StudentDTO> updateStudent(
            @Parameter(description = "Identifiant de l'étudiant.", example = "stu_001")
            @PathVariable String studentId,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "Données de mise à jour de l'étudiant.",
                    content = @Content(schema = @Schema(implementation = UpdateStudentCommand.class)))
            @RequestBody UpdateStudentCommand command
    );

    @Operation(summary = "Supprimer un étudiant",
               description = "Supprime un étudiant du système.")
    @ApiResponse(responseCode = "204", description = "Étudiant supprimé")
    @ApiResponse(responseCode = "404", description = "Étudiant non trouvé")
    @DeleteMapping("/{studentId}")
    ResponseEntity<Void> deleteStudent(
            @Parameter(description = "Identifiant de l'étudiant.", example = "stu_001")
            @PathVariable String studentId
    );
}
```

---

## 7. En-têtes transverses (Cross-cutting Headers)

### 7.1 Objectifs

Les en-têtes transverses servent à :
- corréler les logs et traces (debug & observabilité),
- identifier une requête bout-en-bout (client → gateway → services),
- gérer l'idempotence sur les commandes sensibles.

### 7.2 En-têtes entrants (request)

| Header | Obligatoire | Fournisseur | Usage | Notes |
|---|---|---|---|---|
| `X-Request-Id` | Oui (ou généré si absent) | Client / Gateway / Service | ID unique de requête | Propagé et loggé partout |
| `X-Correlation-Id` | Recommandé | Client / Gateway | Corrélation multi-appels | Stable sur un parcours |
| `traceparent` | Recommandé | Gateway / Service | W3C Trace Context | Propager tel quel |
| `tracestate` | Optionnel | Gateway / Service | W3C Trace Context | Selon provider |
| `Idempotency-Key` | Selon endpoint | Client | Anti retry/double-submit | UUID recommandé |
| `Authorization` | Selon endpoint | Client | AuthN / AuthZ | JWT/OIDC |

### 7.3 En-têtes sortants (response)

| Header | Obligatoire | Usage | Notes |
|---|---|---|---|
| `X-Request-Id` | Oui | Retour de l'ID de requête | Identique au request |
| `X-Correlation-Id` | Recommandé | Retour de l'ID de corrélation | Si présent en request |
| `X-Trace-Id` | Recommandé | Trace ID lisible client | Optionnel si `traceparent` suffit |
| `Retry-After` | Selon cas | Rate limit / backoff | Avec `429` |

### 7.4 Règles de propagation

- **`X-Request-Id`** : si fourni par le client → propager tel quel ; si absent → le service le génère. Doit figurer dans tous les logs et dans `ErrorResponse.requestId`.
- **`X-Correlation-Id`** : si fourni → propager sur tous les appels internes sortants. Pas obligatoire de le générer si absent.
- **`traceparent` / `tracestate`** : propager tel quel. Observabilité basée sur OpenTelemetry.

---

## 8. Idempotency-Key (commandes sensibles)

### 8.1 Règle

`Idempotency-Key` est **obligatoire** sur les endpoints d'écriture à risque : retry, double-submit, finance, irréversible.

### 8.2 Exemples de commandes avec idempotence obligatoire

| Domaine | Endpoints |
|---|---|
| **Paiement** | `POST /trusted/v1/<projet>/payment` (initier) |
| | `POST /trusted/v1/<projet>/payment/{id}/confirm` (confirmer) |
| **Facturation** | `POST /operator/v1/<projet>/billing/invoices` |
| **Transfert / Wallet** | `POST /trusted/v1/<projet>/transfer` |
| | `POST /trusted/v1/<projet>/wallet/debit` |
| | `POST /trusted/v1/<projet>/wallet/credit` |
| **Abonnements** | `POST /trusted/v1/<projet>/subscription` |
| | `POST /trusted/v1/<projet>/subscription/{id}/renew` |

> Cette liste est contractuelle. Tout nouvel endpoint d'écriture dans ces domaines doit être évalué et, par défaut, ajouté.

### 8.3 Comportement attendu

| Cas | Résultat |
|---|---|
| Même `Idempotency-Key` + même payload | Rejouer la même réponse (status + body) |
| Même `Idempotency-Key` + payload différent | `409 Conflict` + `ErrorResponse` avec `IDEMPOTENCY_KEY_REUSE_WITH_DIFFERENT_PAYLOAD` |

---

## 9. Mise en œuvre technique

### 9.1 Plugins Gad Digital

Le projet API **ne contient pas** de package `common`. Les composants transverses sont centralisés dans des plugins :

| Plugin | Fournit |
|---|---|
| **`gd-backend-runtime`** | `ErrorResponse`, `CommonErrorDict`, configuration JWT, filtres cross-cutting (headers), gestion d'erreurs unifiée |
| **`gd-api-conformity`** | Test de conformité `ApiConformityTest` pour valider la structure des contrôleurs et des routes |

### 9.2 Configuration `application.yml`

```yaml
gd:
  backend:
    security:
      jwt-secret: ${JWT_SECRET:please-set-a-secret}
      access-token-expiration-minutes: ${JWT_ACCESS_EXPIRATION:30}
      refresh-token-expiration-minutes: ${JWT_REFRESH_EXPIRATION:4320}
      public-routes:
        - /api/public
        - /api/health
```

### 9.3 Test de conformité

Ajouter un test `ApiConformityTest` basé sur `gd-api-conformity` pour valider que :
- les contrôleurs `@RestController` sont sous `io.gaddigital.*.api`,
- les chemins utilisent le préfixe attendu (`/operator/…`, `/trusted/…`, `/s2s/…`),
- les interfaces de contrat respectent les conventions de nommage.

---

## 10. Récapitulatif — Arbre complet d'un projet

Exemple complet pour le projet **EMI** de Gad Digital, domaines **student** et **game** :

```
io.gaddigital.emi.api/
│
├── student/
│   └── operator/
│       ├── OperatorStudentAPI.java        ← interface de contrat
│       ├── error/
│       │   └── ErrorStudentDict.java      ← enum d'erreurs
│       ├── command/
│       │   ├── CreateStudentCommand.java  ← record
│       │   └── UpdateStudentCommand.java  ← record
│       ├── view/
│       │   └── StudentDetailView.java     ← record
│       └── model/
│           └── StudentDTO.java            ← record
│
├── game/
│   ├── operator/
│   │   ├── OperatorGameAPI.java
│   │   ├── error/
│   │   │   └── ErrorGameDict.java
│   │   ├── command/
│   │   │   ├── CreateGameCommand.java
│   │   │   └── UpdateGameCommand.java
│   │   ├── view/
│   │   │   └── GameDetailView.java
│   │   └── model/
│   │       └── GameDTO.java
│   │
│   ├── trusted/
│   │   ├── TrustedGameAPI.java
│   │   ├── error/
│   │   │   └── ErrorGameDict.java
│   │   ├── command/
│   │   │   └── StartGameSessionCommand.java
│   │   ├── view/
│   │   │   └── GameSessionView.java
│   │   └── model/
│   │       └── GameDTO.java
│   │
│   └── s2s/
│       ├── S2sGameAPI.java
│       ├── error/
│       │   └── ErrorGameDict.java
│       └── model/
│           └── GameDTO.java
│
└── configuration/
    └── operator/
        ├── OperatorConfigurationAPI.java
        ├── error/
        │   └── ErrorConfigurationDict.java
        ├── command/
        │   └── UpdateConfigurationCommand.java
        └── model/
            └── ConfigurationDTO.java
```

---

## 11. Checklist de conformité

Utiliser cette checklist pour valider tout contrat d'API avant livraison :

- [ ] Le package racine respecte `io.gaddigital.[<client>.]<projet>.api`
- [ ] **Pas** de package `common` dans le projet (fourni par les plugins)
- [ ] Les domaines sont des sous-packages directs du package racine
- [ ] Chaque acteur a son propre sous-package (`operator`, `trusted`, `s2s`)
- [ ] L'interface de contrat est nommée `<Actor><Domain>API`
- [ ] Les sous-packages `error`, `command`, `view`, `model` sont présents (selon besoin)
- [ ] L'enum d'erreurs est nommé `Error<Domain>Dict`
- [ ] Les commandes sont nommées `<Verbe><Entité>Command` (records)
- [ ] Les vues sont nommées `<Entité>View` (records)
- [ ] Les DTOs sont nommés `<Entité>DTO` (records)
- [ ] Chaque champ de record porte `@Schema(description, example)`
- [ ] L'interface porte `@Tag` et chaque méthode porte `@Operation` + `@ApiResponse`
- [ ] Les body ne prennent que des `*Command`
- [ ] Les retours sont des `*DTO`, `*View` ou `ErrorResponse`
- [ ] Les path/query params sont des types simples
- [ ] Les URLs respectent `/<actor>/v1/<code_projet>/<domaine>/…`
- [ ] Les URLs sont en kebab-case
- [ ] Les verbes HTTP portent la sémantique REST (GET, POST, PUT, DELETE)
- [ ] `Idempotency-Key` est exigé sur les commandes sensibles
- [ ] `X-Request-Id` est propagé et loggé
- [ ] Le test `ApiConformityTest` (via `gd-api-conformity`) passe

---

## 12. Exemples de requêtes/réponses

### 12.1 Headers

**Request :**
```
X-Request-Id: req_3b1f5f0a
X-Correlation-Id: cor_91d2a1c0
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
Idempotency-Key: 6a3a8f7a-7f8f-4aef-9f86-3dc6f5b5e5a1   (si commande idempotente)
```

**Response :**
```
X-Request-Id: req_3b1f5f0a
X-Correlation-Id: cor_91d2a1c0
X-Trace-Id: 4bf92f3577b34da6a3ce929d0e0e4736
```

### 12.2 Création d'un étudiant

**Request :**
```
POST /operator/v1/emi/student
Content-Type: application/json

{
  "firstName": "Jean",
  "lastName": "Dupont",
  "email": "jean.dupont@example.com",
  "programCode": "INFO_L3"
}
```

**Response (201 Created) :**
```json
{
  "id": "stu_001",
  "firstName": "Jean",
  "lastName": "Dupont",
  "email": "jean.dupont@example.com",
  "programCode": "INFO_L3",
  "status": "ENROLLED"
}
```

### 12.3 Réponse d'erreur

```json
{
  "errorCode": "STUDENT_NOT_FOUND",
  "message": "Student not found.",
  "status": 404,
  "actor": "operator",
  "feature": "student",
  "path": "/operator/v1/emi/student/stu_999",
  "requestId": "req_3b1f5f0a",
  "correlationId": "cor_91d2a1c0",
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "timestamp": "2026-03-31T12:00:00Z",
  "details": {
    "studentId": "stu_999"
  }
}
```
