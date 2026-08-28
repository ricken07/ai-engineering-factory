# Bonnes pratiques de développement – Gad Digital

Ces guidelines décrivent les bonnes pratiques de développement utilisées chez Gad Digital. Elles s’adressent à tous les développeurs et complètent les api-guidelines.

Sommaire
- Conventions de codage
- Noms de commits
- Noms de branches

## 1. Conventions de codage

- Suivre les conventions de codage Java: PascalCase pour les classes, camelCase pour les méthodes et les variables.
Par exemple :
```java
// Classe en PascalCase
public class UserAccount {
    // Variable en camelCase
    private String userName;
    // Méthode en camelCase
    public String getUserName() {
        return userName;
    }
    public void setUserName(String userName) {
        this.userName = userName;
    }
}
```
- Utiliser des noms de variables et de méthodes explicites et significatifs.
Par exemple :
```java
// Mauvais exemple
int a; // Que représente 'a' ?
void calc(int x, int y); // Que fait 'calc' ?
// Bon exemple
int userAge; // Âge de l'utilisateur
void calculateSum(int firstNumber, int secondNumber); // Calcule la somme de deux nombres
```
- Éviter les abréviations ambiguës.
Par exemple :
```java
// Mauvais exemple
int num; // Nombre de quoi ?
String addr; // Adresse de quoi ?
// Bon exemple
int userCount; // Nombre d'utilisateurs
String emailAddress; // Adresse e-mail
```
- Utiliser des commentaires pour expliquer le "pourquoi" du code, pas le "quoi".
Par exemple :
```java
// Mauvais exemple
int count = 0; // Initialiser le compteur à zéro
// Bon exemple
// Utilisé pour compter le nombre d'utilisateurs actifs dans le système
int activeUserCount = 0;
```
- Organiser le code en sections logiques avec des espaces et des commentaires.
Par exemple :
```java
// Section de déclaration des variables
int userCount;
String userName;
// Section des méthodes
public void addUser(String name) {
    // code pour ajouter un utilisateur
}
public void removeUser(String name) {
    // code pour supprimer un utilisateur
}
```
- Limiter la longueur des lignes de code à 150 caractères pour améliorer la lisibilité. Préférer des lignes plus courtes lorsque cela est possible.
Par exemple :
```java
// Mauvais exemple
public void calc(int a, int b, int c, int d, int e, int f, int g, int h, int i, int j) {
    // code
}
// Bon exemple
public void calculateSum(int firstNumber, int secondNumber, int thirdNumber) {
    // code
}

// Ou si possible passé un DTO pour encapsuler les paramètres
public void calculateSum(CalculationParameters params) {
    // code
}
```
- Utiliser des blocs `try-catch` pour gérer les exceptions de manière appropriée.
Par exemple :
```java
try {
    // Code qui peut lancer une exception
    int result = 10 / divisor;
} catch (ArithmeticException e) {
    // Gérer l'exception
    System.out.println("Erreur : Division par zéro.");
}
```

- Éviter les "code smells" tels que les méthodes trop longues, les classes trop grandes, et les duplications de code.
Par exemple :
```java
// Mauvais exemple : Méthode trop longue
public void processUserData() {
    // Beaucoup de code ici
}
// Bon exemple : Diviser en plusieurs méthodes
public void processUserData() {
    validateUserData();
    saveUserData();
}
private void validateUserData() {
    // Validation du code
}
private void saveUserData() {
    // Sauvegarde du code
}
```
- Utiliser des structures de données appropriées (List, Set, Map) en fonction des besoins.
Par exemple :
```java
// Utiliser une List pour une collection ordonnée avec des doublons
List<String> userNames = new ArrayList<>();
// Utiliser un Set pour une collection unique sans ordre
Set<String> uniqueUserNames = new HashSet<>();
// Utiliser une Map pour une association clé-valeur
Map<String, Integer> userAgeMap = new HashMap<>();
```
- Utiliser les Java records pour les classes immuables simples.
Par exemple :
```java
// Mauvais exemple : Classe mutable
public class User {
    private String name;
    public String getName() {
        return name;
    }
    public void setName(String name) {
        this.name = name;
    }
}
// Bon exemple : Classe immuable avec record
public record User(String name) {}
```
- Utiliser les Optional pour les valeurs pouvant être absentes.
- Par exemple :
```java
// Mauvais exemple : Utilisation de null
public String getUserEmail(User user) {
    if (user != null) {
        return user.getEmail();
    }
    return null;
}
// Bon exemple : Utilisation d'Optional
public Optional<String> getUserEmail(User user) {
    return Optional.ofNullable(user).map(User::getEmail);
}
```
- Utiliser les streams pour les opérations sur les collections.
Par exemple :
```java
// Mauvais exemple : Boucle for traditionnelle
List<String> names = new ArrayList<>();
for (String name : names) {
    System.out.println(name);
}
// Bon exemple : Utilisation de streams
names.stream().forEach(System.out::println);
```
- Utiliser les annotations de validation (jakarta.validation) pour valider les entrées.
Par exemple :
```java
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
public class User {
    @NotNull
    private String name;

    @Size(min = 5, max = 50)
    private String email;

    // getters et setters
}
```

## 2. Noms de commits

Le nom de chaque commit doit être conventionnel et suivre les règles suivantes :
- Utiliser l'impératif présent pour décrire l'action effectuée.
- Limiter la longueur du message de commit à 50 caractères pour le titre.
- Ajouter une description détaillée dans le corps du commit si nécessaire, en séparant le titre et le corps par une ligne vide.
- Utiliser des préfixes pour catégoriser les commits, tels que :
  - `feat:` pour une nouvelle fonctionnalité
  - `fix:` pour une correction de bug
  - `docs:` pour des modifications de documentation
  - `style:` pour des modifications de style (formatage, espaces, etc.)
  - `refactor:` pour des modifications de code sans ajout de fonctionnalité ni correction de bug
  - `test:` pour des ajouts ou modifications de tests
  - `chore:` pour des tâches de maintenance (mise à jour de dépendances, configuration, etc.)
- Exemple de message de commit :
```
feat: ajouter la fonctionnalité de recherche avancée
Ajoute une nouvelle fonctionnalité permettant aux utilisateurs de rechercher des articles en utilisant des filtres avancés tels que la date, la catégorie et l'auteur.
```

```
fix: corriger le bug de connexion utilisateur
Corrige un problème où les utilisateurs ne pouvaient pas se connecter après une mise à jour récente.
```

## 3. Noms de branches

Le nom de chaque branche doit être conventionnel et suivre les règles suivantes :
- Utiliser des noms de branches courts, explicites et en minuscules.
- Utiliser des tirets (-) pour séparer les mots.
- Inclure un préfixe pour indiquer le type de branche, tel que :
  - `feature/` pour une nouvelle fonctionnalité
  - `bugfix/` pour une correction de bug
  - `hotfix/` pour une correction urgente en production
  - `release/` pour une branche de préparation de version
  - `chore/` pour des tâches de maintenance
- Inclure un identifiant de ticket ou de tâche si applicable (par exemple, un numéro JIRA ou GitLab).
- Exemple de nom de branche :
```
feature/advanced-search
bugfix/login-issue
hotfix/payment-error
release/v1.2.0
chore/update-dependencies
```
