# Gad Digital -- Guide de Developpement d'Applications (APP)

> **Ce document est la specification de reference** pour concevoir et implementer les applications
> qui consomment et implémentent les contrats d'API chez Gad Digital.
> Il s'adresse aux développeurs **et aux agents IA** qui génèrent du code.
> Toute application produite doit être conforme à ce guide.

| Propriete | Valeur |
|---|---|
| **Runtime** | Java 25 |
| **Framework** | Spring Boot 4.x - Spring Framework 7.x |
| **Style architectural** | Actor Pattern + Contrats API immutables + Layered architecture |
| **Persistance** | Spring Data JPA / Hibernate |
| **Mapping** | MapStruct ou mappers manuels (les deux sont acceptes) |
| **Plugins communs** | `gd-backend-runtime` (JWT, filtres, gestion d'erreurs) - `gd-common` (Actor, TokenDTO, PageResult) |
| **Contrat API** | Defini dans un projet `*-api` separe -- voir `api-guidelines.md` |

---

## 1. Convention de nommage des packages

### 1.1 Package racine du projet

Le projet APP suit la **meme logique** que le projet API, mais le package racine se termine
par `.app` au lieu de `.api`.

| Type de projet | Format du package racine | Exemple |
|---|---|---|
| Projet **client** | `io.gaddigital.<code_client>.<code_projet>.app` | `io.gaddigital.kabs.okl.app` |
| Projet **Gad Digital** | `io.gaddigital.<code_projet>.app` | `io.gaddigital.emi.app` |

> **Règle :** le package racine se termine toujours par `.app`.
> Dans la suite de ce document, `<root>` désigne le package racine du projet
> (ex : `io.gaddigital.emi.app` ou `io.gaddigital.kabs.okl.app`).

### 1.2 Correspondance API / APP

| Projet API | Projet APP |
|---|---|
| `io.gaddigital.emi.api` | `io.gaddigital.emi.app` |
| `io.gaddigital.kabs.okl.api` | `io.gaddigital.kabs.okl.app` |

Le projet APP **depend** du projet API (en tant que dependance Maven) et implemente ses contrats.

### 1.3 Identifiants

| Element | Casse | Exemples |
|---|---|---|
| `<code_client>` | lowercase | `kabs`, `bgfi` |
| `<code_projet>` | lowercase | `okl`, `emi`, `drs` |
| Packages | lowercase, point-separe | `io.gaddigital.emi.app.impl.game` |

---

## 2. Architecture en couches

Le projet APP est organise en **5 sous-packages principaux** sous le package racine :

```
<root>/
+-- impl/         <- Implementation des contrats d'API (composants)
+-- business/     <- Logique metier (services, use cases, mappers)
+-- jpa/          <- Couche persistance (entites JPA, repositories)
+-- config/       <- Configuration Spring de l'application
+-- util/         <- Utilitaires specifiques a l'application
```

| Package | Responsabilite | Depend de |
|---|---|---|
| `impl` | Implemente les interfaces de contrat d'API (composants Spring) | `business`, projet API |
| `business` | Logique metier, orchestration, mapping DTO / Entity | `jpa`, projet API |
| `jpa` | Entites JPA, repositories Spring Data | -- (couche la plus basse) |
| `config` | Beans Spring, configurations applicatives | Tous les packages si necessaire |
| `util` | Classes utilitaires specifiques au projet | -- |

> **Règle de dependence :** `impl` -> `business` -> `jpa`. Les dépendances inverses sont **interdites**.
> Le package `jpa` ne doit jamais dépendre de `business` ou `impl`.
> Le package `business` ne doit jamais dépendre de `impl`.

---

## 3. Package `impl` — Implementation des contrats d'API

### 3.1 Organisation par domaine

Le package `impl` est organisé en **sous-packages par domaine**, reflétant la structure du projet API :

```
<root>.impl/
+-- game/
|   +-- OperatorGameImpl.java
+-- billing/
|   +-- TrustedBillingImpl.java
+-- student/
    +-- OperatorStudentImpl.java
    +-- TrustedStudentImpl.java
```

### 3.2 Convention de nommage

Les classes d'implémentation suivent la convention : **`<Actor><Domain>Impl`**

| Contrat API (interface) | Implementation APP (classe) | Package |
|---|---|---|
| `OperatorGameAPI` | `OperatorGameImpl` | `<root>.impl.game` |
| `TrustedBillingAPI` | `TrustedBillingImpl` | `<root>.impl.billing` |
| `S2sGameAPI` | `S2sGameImpl` | `<root>.impl.game` |

> **Règle :** le suffixe `API` du contrat est remplace par `Impl`.
> Plusieurs acteurs du meme domaine cohabitent dans le meme sous-package domaine.

### 3.3 Structure d'une classe d'implémentation

```java
package io.gaddigital.emi.app.impl.game;

import io.gaddigital.emi.api.game.operator.OperatorGameAPI;
import io.gaddigital.emi.api.game.operator.command.CreateGameCommand;
import io.gaddigital.emi.api.game.operator.model.GameDTO;
import io.gaddigital.emi.api.game.operator.view.GameDetailView;
import io.gaddigital.emi.app.business.game.usecase.CreateGameUseCase;
import io.gaddigital.emi.app.business.game.usecase.GetGameDetailUseCase;
import io.gaddigital.emi.app.business.game.usecase.ListGamesUseCase;

import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class OperatorGameImpl implements OperatorGameAPI {

    private final ListGamesUseCase listGamesUseCase;
    private final GetGameDetailUseCase getGameDetailUseCase;
    private final CreateGameUseCase createGameUseCase;

    public OperatorGameImpl(ListGamesUseCase listGamesUseCase,
                            GetGameDetailUseCase getGameDetailUseCase,
                            CreateGameUseCase createGameUseCase) {
        this.listGamesUseCase = listGamesUseCase;
        this.getGameDetailUseCase = getGameDetailUseCase;
        this.createGameUseCase = createGameUseCase;
    }

    @Override
    public ResponseEntity<List<GameDTO>> listGames() {
        return ResponseEntity.ok(listGamesUseCase.execute());
    }

    @Override
    public ResponseEntity<GameDetailView> getGame(String gameId) {
        return ResponseEntity.ok(getGameDetailUseCase.execute(gameId));
    }

    @Override
    public ResponseEntity<GameDTO> createGame(CreateGameCommand command) {
        return ResponseEntity.status(201).body(createGameUseCase.execute(command));
    }
}
```

**Caracteristiques obligatoires :**
- Annotee `@Component` (le `@RestController` est porte par le contrat d'API, pas par l'implementation)
- Implemente l'interface de contrat d'API correspondante
- **Injecte uniquement des `*UseCase`** -- jamais de `*Service` ou `*Repository` directement
- **Aucune logique metier** -- delegue immediatement aux use cases
- **Aucune annotation Swagger** -- les annotations sont deja sur le contrat d'API
- **Aucune annotation de mapping HTTP** (`@GetMapping`, `@PostMapping`, etc.) -- heritees du contrat

---

## 4. Package `business` -- Logique metier

### 4.1 Organisation par domaine

Le package `business` est organise en **sous-packages par domaine** :

```
<root>.business/
+-- game/
|   +-- service/
|   |   +-- GameService.java
|   +-- usecase/
|   |   +-- CreateGameUseCase.java
|   |   +-- UpdateGameUseCase.java
|   +-- mapper/
|       +-- GameMapper.java
+-- billing/
|   +-- service/
|   |   +-- BillingService.java
|   +-- usecase/
|   |   +-- CreateInvoiceUseCase.java
|   +-- mapper/
|       +-- BillingMapper.java
+-- student/
    +-- service/
    |   +-- StudentService.java
    +-- usecase/
    |   +-- EnrollStudentUseCase.java
    +-- mapper/
        +-- StudentMapper.java
```

### 4.2 Sous-package `service`

Le service fournit des **operations reutilisables** pour un domaine. Il encapsule la logique
de lecture et les operations simples. Les services sont consommes par les use cases (jamais par les `*Impl`).

**Convention de nommage :** `<Domain>Service`

| Domaine | Classe | Package |
|---|---|---|
| game | `GameService` | `<root>.business.game.service` |
| billing | `BillingService` | `<root>.business.billing.service` |
| student | `StudentService` | `<root>.business.student.service` |

**Caracteristiques :**
- Annotee `@Service`
- Un seul service par domaine (tous acteurs confondus)
- Peut utiliser les **repositories** et les **mappers**
- **Ne peut PAS utiliser de `*UseCase`** (dependance inverse interdite)
- Gere les transactions (`@Transactional`) si necessaire

```java
package io.gaddigital.emi.app.business.game.service;

import io.gaddigital.emi.api.game.operator.model.GameDTO;
import io.gaddigital.emi.api.game.operator.view.GameDetailView;
import io.gaddigital.emi.app.business.game.mapper.GameMapper;
import io.gaddigital.emi.app.jpa.game.GameRepository;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class GameService {

    private final GameRepository gameRepository;
    private final GameMapper gameMapper;

    public GameService(GameRepository gameRepository,
                       GameMapper gameMapper) {
        this.gameRepository = gameRepository;
        this.gameMapper = gameMapper;
    }

    public List<GameDTO> listGames() {
        return gameRepository.findAll().stream()
                .map(gameMapper::toDTO)
                .toList();
    }

    public GameDetailView getGameDetail(String gameId) {
        var entity = gameRepository.findByGameId(gameId)
                .orElseThrow();
        return gameMapper.toDetailView(entity);
    }
}
```

### 4.3 Sous-package `usecase`

Un use case encapsule **une action metier spécifique**. C'est le **point d'entrée principal** appelé
par les `*Impl`. Il orchestre la logique en combinant services, repositories, mappers et autres use cases.

**Convention de nommage :** `<Action><Domain>UseCase`

| Action | Classe | Package |
|---|---|---|
| Creer un jeu | `CreateGameUseCase` | `<root>.business.game.usecase` |
| Mettre a jour la config | `UpdateConfigurationUseCase` | `<root>.business.configuration.usecase` |
| Inscrire un etudiant | `EnrollStudentUseCase` | `<root>.business.student.usecase` |

**Caracteristiques :**
- Annotee `@Service`
- Une seule responsabilite (Single Responsibility Principle)
- Methode principale : `execute(...)` ou nom descriptif
- Peut utiliser les **repositories**, les **services**, les **mappers** et d'autres **use cases**

```java
package io.gaddigital.emi.app.business.game.usecase;

import io.gaddigital.emi.api.game.operator.command.CreateGameCommand;
import io.gaddigital.emi.api.game.operator.model.GameDTO;
import io.gaddigital.emi.app.business.game.mapper.GameMapper;
import io.gaddigital.emi.app.jpa.game.GameEntity;
import io.gaddigital.emi.app.jpa.game.GameRepository;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CreateGameUseCase {

    private final GameRepository gameRepository;
    private final GameMapper gameMapper;

    public CreateGameUseCase(GameRepository gameRepository, GameMapper gameMapper) {
        this.gameRepository = gameRepository;
        this.gameMapper = gameMapper;
    }

    @Transactional
    public GameDTO execute(CreateGameCommand command) {
        var entity = gameMapper.toEntity(command);
        var saved = gameRepository.save(entity);
        return gameMapper.toDTO(saved);
    }
}
```

### 4.4 Sous-package `mapper`

Les mappers assurent la **conversion entre les modèles** des différentes couches :
- `Entity` (JPA) vers `*DTO` (contrat API)
- `Entity` (JPA) vers `*View` (contrat API)
- `*Command` (contrat API) vers `Entity` (JPA)

**Convention de nommage :** `<Domain>Mapper`

| Domaine | Classe | Package |
|---|---|---|
| game | `GameMapper` | `<root>.business.game.mapper` |
| billing | `BillingMapper` | `<root>.business.billing.mapper` |

**Deux approches acceptees :**

#### Option A — MapStruct (recommande pour les projets complexes)

```java
package io.gaddigital.emi.app.business.game.mapper;

import io.gaddigital.emi.api.game.operator.model.GameDTO;
import io.gaddigital.emi.api.game.operator.view.GameDetailView;
import io.gaddigital.emi.api.game.operator.command.CreateGameCommand;
import io.gaddigital.emi.app.jpa.game.GameEntity;

import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring")
public interface GameMapper {

    GameDTO toDTO(GameEntity entity);

    GameDetailView toDetailView(GameEntity entity);

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "status", constant = "ACTIVE")
    GameEntity toEntity(CreateGameCommand command);
}
```

#### Option A.2 -- MapStruct avec décorateur (customisation avancée)

Lorsqu'un mapping nécessite une logique supplémentaire (appels a d'autres services, calculs,
enrichissement conditionnel), on utilise le pattern **Decorator** de MapStruct.

**Convention de nommage :** `<Domain>MapperDecorator`

```java
package io.gaddigital.emi.app.business.game.mapper;

import io.gaddigital.emi.api.game.operator.model.GameDTO;
import io.gaddigital.emi.api.game.operator.view.GameDetailView;
import io.gaddigital.emi.api.game.operator.command.CreateGameCommand;
import io.gaddigital.emi.app.jpa.game.GameEntity;

import org.mapstruct.DecoratedWith;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring")
@DecoratedWith(GameMapperDecorator.class)
public interface GameMapper {

    GameDTO toDTO(GameEntity entity);

    GameDetailView toDetailView(GameEntity entity);

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "status", constant = "ACTIVE")
    GameEntity toEntity(CreateGameCommand command);
}
```

```java
package io.gaddigital.emi.app.business.game.mapper;

import io.gaddigital.emi.api.game.operator.view.GameDetailView;
import io.gaddigital.emi.app.jpa.game.GameEntity;
import io.gaddigital.emi.app.jpa.game.GameSessionRepository;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;

public abstract class GameMapperDecorator implements GameMapper {

    @Autowired
    @Qualifier("delegate")
    private GameMapper delegate;

    @Autowired
    private GameSessionRepository gameSessionRepository;

    @Override
    public GameDetailView toDetailView(GameEntity entity) {
        // Appel au mapper génère pour les champs simples
        var view = delegate.toDetailView(entity);
        // Enrichissement avec une donnee calculée
        int activeSessions = gameSessionRepository.countActiveByGameId(entity.getId());
        return new GameDetailView(
                view.id(), view.name(), view.type(),
                view.status(), activeSessions
        );
    }
}
```

**Quand utiliser le decorateur :**
- Enrichissement avec des donnees provenant d'autres repositories ou services
- Logique conditionnelle complexe non exprimable via `@Mapping`
- Post-traitement sur les objets mappes (calculs, formatage)

> **Règle :** le décorateur reste dans le meme package `mapper` que l'interface MapStruct.
> Il ne doit pas contenir de logique metier — uniquement de la logique de mapping/enrichissement.

#### Option B — Mapper manuel

```java
package io.gaddigital.emi.app.business.game.mapper;

import io.gaddigital.emi.api.game.operator.model.GameDTO;
import io.gaddigital.emi.api.game.operator.view.GameDetailView;
import io.gaddigital.emi.api.game.operator.command.CreateGameCommand;
import io.gaddigital.emi.app.jpa.game.GameEntity;

import org.springframework.stereotype.Component;

@Component
public class GameMapper {

    public GameDTO toDTO(GameEntity entity) {
        return new GameDTO(entity.getId(), entity.getName(), entity.getStatus());
    }

    public GameDetailView toDetailView(GameEntity entity) {
        return new GameDetailView(
                entity.getId(), entity.getName(),
                entity.getType(), entity.getStatus(),
                entity.getActiveSessions()
        );
    }

    public GameEntity toEntity(CreateGameCommand command) {
        var entity = new GameEntity();
        entity.setName(command.name());
        entity.setType(command.type());
        entity.setStatus("ACTIVE");
        return entity;
    }
}
```

---

## 5. Package `jpa` -- Couche persistance

### 5.1 Organisation par domaine

Le package `jpa` est organise en **sous-packages par domaine** :

```
<root>.jpa/
+-- game/
|   +-- GameEntity.java
|   +-- GameRepository.java
+-- billing/
|   +-- InvoiceEntity.java
|   +-- InvoiceRepository.java
+-- student/
    +-- StudentEntity.java
    +-- StudentRepository.java
```

### 5.2 Entités JPA

**Convention de nommage :** `<Domain>Entity`

| Domaine | Classe | Package |
|---|---|---|
| game | `GameEntity` | `<root>.jpa.game` |
| billing | `InvoiceEntity` | `<root>.jpa.billing` |
| student | `StudentEntity` | `<root>.jpa.student` |

**Caractéristiques obligatoires :**
- Annotée `@Entity` et `@Table`
- Utilise les annotations JPA standard (`@Id`, `@GeneratedValue`, `@Column`, etc.)
- Pas de logique metier dans l'entité
- Les relations (`@OneToMany`, `@ManyToOne`, etc.) sont gérées avec des strategies de fetch appropriées

```java
package io.gaddigital.emi.app.jpa.game;

import jakarta.persistence.*;

@Entity
@Table(name = "games")
public class GameEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private String type;

    @Column(nullable = false)
    private String status;

    @Column(name = "active_sessions")
    private int activeSessions;

    // Constructeur par défaut requis par JPA
    protected GameEntity() {}

    // Getters et Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public int getActiveSessions() { return activeSessions; }
    public void setActiveSessions(int activeSessions) { this.activeSessions = activeSessions; }
}
```

### 5.3 Repositories Spring Data

**Convention de nommage :** `<Domain>Repository`

| Domaine | Interface | Package |
|---|---|---|
| game | `GameRepository` | `<root>.jpa.game` |
| billing | `InvoiceRepository` | `<root>.jpa.billing` |
| student | `StudentRepository` | `<root>.jpa.student` |

```java
package io.gaddigital.emi.app.jpa.game;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface GameRepository extends JpaRepository<GameEntity, String> {

    Optional<GameEntity> findByGameId(String gameId);
}
```

---

## 6. Package `config` -- Configuration

Le package `config` contient les **classes de configuration Spring** spécifiques a l'application.

```
<root>.config/
+-- SecurityConfig.java
+-- JpaConfig.java
+-- WebConfig.java
```

**Convention de nommage :** `<Concern>Config`

**Caractéristiques :**
- Annotées `@Configuration`
- Pas de logique metier
- Centralisent la configuration Spring Beans, securite, JPA, etc.

```java
package io.gaddigital.emi.app.config;

import org.springframework.context.annotation.Configuration;

@Configuration
public class SecurityConfig {
    // Configuration de la securite spécifique a l'application
}
```

---

## 7. Package `util` — Utilitaires

Le package `util` contient les **classes utilitaires spécifiques** à l'application.

```
<root>.util/
+-- DateUtils.java
+-- SlugGenerator.java
+-- ValidationHelper.java
```

**Caractéristiques :**
- Classes avec méthodes `static` ou beans Spring
- Pas de logique metier
- Utilitaires partages **uniquement au sein de cette application**
- Les utilitaires transverses (communs a plusieurs projets) vont dans `gd-common`

---

## 8. Vue d'ensemble -- Arborescence complete

Exemple complet pour un projet `io.gaddigital.emi.app` avec deux domaines (`game`, `billing`) :

```
io.gaddigital.emi.app/
|
+-- impl/                                   <- Couche implementation (composants)
|   +-- game/
|   |   +-- OperatorGameImpl.java           <- implements OperatorGameAPI
|   |   +-- TrustedGameImpl.java            <- implements TrustedGameAPI
|   +-- billing/
|       +-- TrustedBillingImpl.java         <- implements TrustedBillingAPI
|
+-- business/                               <- Couche metier
|   +-- game/
|   |   +-- service/
|   |   |   +-- GameService.java            <- Service principal du domaine game
|   |   +-- usecase/
|   |   |   +-- CreateGameUseCase.java      <- Use case : creer un jeu
|   |   |   +-- UpdateGameUseCase.java      <- Use case : mettre a jour un jeu
|   |   +-- mapper/
|   |       +-- GameMapper.java             <- Mapping Entity / DTO / View
|   +-- billing/
|       +-- service/
|       |   +-- BillingService.java
|       +-- usecase/
|       |   +-- CreateInvoiceUseCase.java
|       +-- mapper/
|           +-- BillingMapper.java
|
+-- jpa/                                    <- Couche persistance
|   +-- game/
|   |   +-- GameEntity.java                 <- Entite JPA
|   |   +-- GameRepository.java             <- Repository Spring Data
|   +-- billing/
|       +-- InvoiceEntity.java
|       +-- InvoiceRepository.java
|
+-- config/                                 <- Configuration Spring
|   +-- SecurityConfig.java
|   +-- JpaConfig.java
|
+-- util/                                   <- Utilitaires
    +-- DateUtils.java
```

---

## 9. Règles de nommage -- Resume

### 9.1 Classes d'implémentation

| Contrat API | Classe d'implementation | Package |
|---|---|---|
| `<Actor><Domain>API` | `<Actor><Domain>Impl` | `<root>.impl.<domain>` |

### 9.2 Services

| Convention | Exemple | Package |
|---|---|---|
| `<Domain>Service` | `GameService` | `<root>.business.<domain>.service` |

### 9.3 Use Cases

| Convention | Exemple | Package |
|---|---|---|
| `<Action><Domain>UseCase` | `CreateGameUseCase` | `<root>.business.<domain>.usecase` |

### 9.4 Mappers

| Convention | Exemple | Package |
|---|---|---|
| `<Domain>Mapper` | `GameMapper` | `<root>.business.<domain>.mapper` |

### 9.5 Entites JPA

| Convention | Exemple | Package |
|---|---|---|
| `<Domain>Entity` | `GameEntity` | `<root>.jpa.<domain>` |

### 9.6 Repositories

| Convention | Exemple | Package |
|---|---|---|
| `<Domain>Repository` | `GameRepository` | `<root>.jpa.<domain>` |

### 9.7 Configuration

| Convention | Exemple | Package |
|---|---|---|
| `<Concern>Config` | `SecurityConfig` | `<root>.config` |

---

## 10. Flux de donnees — Du contrat a la base

Voici le flux typique d'un appel API dans l'application :

```
Client HTTP
    |
    v
+-------------------------------+
|  OperatorGameImpl             |  <- impl (composant @Component)
|  implements OperatorGameAPI   |
+---------------+---------------+
                | delegue aux use cases
                v
+-------------------------------+
|  CreateGameUseCase            |  <- business/usecase
|  logique metier specifique    |
+-------+-----------+-----------+
        |           |
        v           v
+-------------+  +--------------+
| GameService |  | GameMapper   |  <- business/service + business/mapper
+------+------+  +--------------+
       |                |
       v                v
+-------------------------------+
|  GameRepository               |  <- jpa
|  GameEntity                   |
+-------------------------------+
                |
                v
         Base de donnees
```

---

## 11. Règles de dependence entre couches

```
impl  ------->  business/usecase  ------->  business/service  ------->  jpa
                     |                           |
                     +---> jpa                   +---> jpa
                     |
                     +---> business/mapper
                     |
                     +---> autres use cases
```

### 11.1 Règles de dependence entre composants

| Source | Cible | Autorise ? | Description |
|---|---|---|---|
| `*Impl` | `*UseCase` | **Oui** | L'implementation delegue aux use cases |
| `*Impl` | `*Service` | **NON** | L'impl ne consomme que des use cases |
| `*Impl` | `*Repository` | **NON** | Jamais d'acces direct a la persistance |
| `*UseCase` | `*Repository` | **Oui** | Le use case accede aux repositories |
| `*UseCase` | `*Service` | **Oui** | Le use case peut utiliser des services |
| `*UseCase` | `*UseCase` | **Oui** | Un use case peut composer d'autres use cases |
| `*UseCase` | `*Mapper` | **Oui** | Le use case utilise les mappers |
| `*Service` | `*Repository` | **Oui** | Le service accede aux repositories |
| `*Service` | `*Mapper` | **Oui** | Le service utilise les mappers |
| `*Service` | `*UseCase` | **NON** | Le service ne peut pas appeler de use cases |
| `*Service` | `*Service` | **Oui** | Un service peut utiliser d'autres services |

### 11.2 Règles de dependence entre couches

| Regle | Description |
|---|---|
| `impl` vers `business` | Autorise -- L'implementation delegue aux use cases |
| `impl` vers `jpa` | **Interdit** -- passer par `business` |
| `business` vers `jpa` | Autorise -- Les use cases et services utilisent les repositories |
| `business` vers `impl` | **Interdit** -- dependance inverse |
| `jpa` vers `business` | **Interdit** -- dependance inverse |
| `jpa` vers `impl` | **Interdit** -- dependance inverse |
| `impl` vers projet API | Autorise -- Pour implementer les interfaces de contrat |
| `business` vers projet API | Autorise -- Pour utiliser les DTO, Command, View |
| `jpa` vers projet API | **Interdit** -- la couche JPA est independante du contrat API |
| `config` vers tout | Autorise -- Configuration transverse |
| `util` vers aucun | Autorise -- Utilitaires autonomes |

---

## 12. Anti-patterns a éviter

| Anti-pattern | Bonne pratique |
|---|---|
| Logique metier dans `*Impl` | Deleguer au `*Service` ou `*UseCase` |
| Annotations Swagger dans `*Impl` | Deja sur le contrat API (heritage) |
| `@GetMapping`/`@PostMapping` dans `*Impl` | Heritees de l'interface API |
| Repository injecte dans `*Impl` | Passer par le service business |
| Entity utilisee comme DTO de retour | Utiliser les `*DTO`/`*View` du contrat API |
| DTO du contrat API utilise comme entite JPA | Creer une `*Entity` dans le package `jpa` |
| Mapper dans le package `impl` | Mapper dans `business.<domain>.mapper` |
| Service qui connait `HttpServletRequest` | Le service ne depend pas de la couche web |
| Use case avec plusieurs responsabilites | Un use case = une action metier |
| Package `common` dans l'application | Utiliser `gd-common` ou `util` |

---

## 13. Checklist de conformité

Avant de valider un projet APP, verifier :

- [ ] Le package racine se termine par `.app`
- [ ] Les classes `*Impl` sont dans `<root>.impl.<domain>`
- [ ] Chaque `*Impl` implémenté une interface `*API` du projet API
- [ ] Chaque `*Impl` est annotée `@Component`
- [ ] Les `*Impl` ne contiennent aucune annotation Swagger ou mapping HTTP
- [ ] Les `*Service` sont dans `<root>.business.<domain>.service`
- [ ] Les `*UseCase` sont dans `<root>.business.<domain>.usecase`
- [ ] Les `*Mapper` sont dans `<root>.business.<domain>.mapper`
- [ ] Les `*Entity` sont dans `<root>.jpa.<domain>`
- [ ] Les `*Repository` sont dans `<root>.jpa.<domain>`
- [ ] Les `*Config` sont dans `<root>.config`
- [ ] Aucune dependence inverse entre les couches
- [ ] Aucun package `common` dans le projet
