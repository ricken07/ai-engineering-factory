# Gad Digital Guidelines

Ce projet regroupe les guides de référence utilisés pour standardiser la conception et l'implémentation des projets backend chez Gad Digital.

L'objectif du dépôt est de fournir un cadre commun, lisible et exploitable aussi bien par les développeurs que par les agents IA qui produisent du code. Les conventions décrites ici doivent servir de base pour garantir une architecture cohérente, des contrats homogènes et une implémentation conforme sur l'ensemble des projets.

## Objectif

Le projet `guidelines` définit les règles de développement pour :

- concevoir des contrats d'API backend de manière uniforme ;
- implémenter les applications Spring Boot qui consomment et exposent ces contrats ;
- imposer des conventions de nommage, de packaging et d'architecture partagées ;
- réduire les écarts d'implémentation entre équipes, projets clients et projets internes ;
- fournir une base de référence unique pour la génération de code assistée par IA.

## Contenu du dépôt

### [api-guidelines.md](./api-guidelines.md)

Guide de développement des projets API.

Ce document couvre notamment :

- la structure des packages racine et des domaines ;
- l'Actor Pattern (`operator`, `trusted`, `s2s`) ;
- la définition des contrats REST ;
- les conventions autour des `Command`, `DTO`, `View` et dictionnaires d'erreurs ;
- les règles de routage et de documentation OpenAPI.

### [app-guidelines.md](./app-guidelines.md)

Guide de développement des projets APP.

Ce document décrit notamment :

- la correspondance entre un projet API et son projet APP ;
- l'architecture en couches (`impl`, `business`, `jpa`, `config`, `util`) ;
- les responsabilités de chaque couche ;
- les conventions de nommage des implémentations, services, use cases et mappers ;
- les règles de dépendance et d'organisation du code applicatif.

## À qui s'adresse ce dépôt

Ce référentiel s'adresse à :

- l'équipe de développement backend ;
- les contributeurs amenés à créer de nouveaux projets API ou APP ;
- les relecteurs techniques qui vérifient la conformité des implémentations ;
- les agents IA utilisés pour générer, compléter ou refactorer du code.

## Utilisation attendue

Avant de démarrer un nouveau projet ou d'ajouter un nouveau domaine métier :

1. consulter le guide API pour définir correctement le contrat du projet `*-api` ;
2. consulter le guide APP pour implémenter le projet `*-app` conforme au contrat ;
3. appliquer ces conventions dès la création des packages, classes et endpoints ;
4. considérer ces documents comme la référence prioritaire en cas d'arbitrage technique sur la structure du code.

## Positionnement du projet

`guidelines` n'est pas un projet applicatif ni une bibliothèque runtime. C'est un référentiel documentaire de normes de développement destiné à aligner les pratiques d'architecture et de production de code au sein de l'écosystème Gad Digital.
