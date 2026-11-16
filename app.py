import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from pathlib import Path
import pandas as pd

# python -m streamlit run app.py

# Chargement des données
chemin = Path(
    r"C:\Users\Sievic\OneDrive\Bureau\projet\Datathon\donnees\bocage"
)

evolution = gpd.read_file(chemin / "evolution_bocage.gpkg", layer="evolution")
etat_bocage = gpd.read_file(chemin / "etat_bocage.gpkg", layer="etat_bocage")

zones_boisees = gpd.read_file(Path(r"C:\Users\Sievic\OneDrive\Bureau\projet\Datathon\resultats\indicateurs_zones_boisees.gpkg"))

biodiversite = pd.read_csv(Path(r"C:\Users\Sievic\OneDrive\Bureau\projet\Datathon\livraison_robin_biodiversite\indicateurs\indicateurs_biodiversite_bocage.csv"))


# Conversion en coordonnées géographiques pour Folium
evolution = evolution.to_crs(epsg=4326)
etat_bocage = etat_bocage.to_crs(epsg=4326)




###############################################################################################################################
# calcul des différents scores

etat_bocage["score_densite"] = (
    etat_bocage["indicateur_lineaire"]
    .rank(ascending=False, pct=True) * 100
)


etat_bocage["score_coherence"] = (
    etat_bocage["indicateur_coherence"]
    .rank(ascending=False, pct=True) * 100
)


evolution["variation_annuelle_lineaire"] = (
    (evolution["indicateur_lineaire_finale"]
     - evolution["indicateur_lineaire_initiale"])
    / (evolution["annee_finale"] - evolution["annee_initiale"])
)

degradation_lineaire = (
    -evolution["variation_annuelle_lineaire"]
).clip(lower=0) # empêche les valeurs négatives

score_lineaire = degradation_lineaire.rank(pct=True) * 100

evolution["score_evolution_lineaire"] = score_lineaire.where(
    degradation_lineaire > 0, 0
)



evolution["variation_annuelle_coherence"] = (
    (evolution["indicateur_coherence_finale"]
     - evolution["indicateur_coherence_initiale"])
    / (evolution["annee_finale"] - evolution["annee_initiale"])
)

degradation_coherence = (
    -evolution["variation_annuelle_coherence"]
).clip(lower=0)

score_coherence = degradation_coherence.rank(pct=True) * 100

evolution["score_evolution_coherence"] = score_coherence.where(
    degradation_coherence > 0, 0
)


cles = ["departement", "id_cercle_ref"]     # identifie chaque cercle dans les deux fichiers

scores_evolution = evolution[               # ne conserve que les identifiants et les deux scores
    cles + [
        "score_evolution_lineaire",
        "score_evolution_coherence"
    ]
]

score_bocage = etat_bocage.merge(           # merge associe les scores historiques aux cercles actuels
    scores_evolution,
    on=cles,
    how="left"                              # conserve tous les cercles de l'état actuel, même ceux qui n'ont pas d'historique
)


# Score synthétique des haies
indicateurs_haies = [
    "score_densite",
    "score_coherence",
    "score_evolution_lineaire",
    "score_evolution_coherence"
]

score_bocage["score_haies"] = score_bocage[
    indicateurs_haies
].mean(axis=1)




####################
# calcul du score pour les zones boisées

degradation_moyenne = (
    -zones_boisees["variation_annuelle_moyenne"]
).clip(lower=0)

degradation_recente = (
    -zones_boisees["variation_derniere_periode"]
).clip(lower=0)


# Classement des pertes entre 0 et 100
# Score de dégradation moyenne
zones_boisees["score_degradation_moyenne"] = 0.0

masque = degradation_moyenne > 0

zones_boisees.loc[masque, "score_degradation_moyenne"] = (
    degradation_moyenne[masque].rank(pct=True) * 100
)


# Score de dégradation récente
zones_boisees["score_degradation_recente"] = 0.0

masque = degradation_recente > 0

zones_boisees.loc[masque, "score_degradation_recente"] = (
    degradation_recente[masque].rank(pct=True) * 100
)


# Score global des zones boisées
zones_boisees["score_zones_boisees"] = zones_boisees[
    ["score_degradation_moyenne", "score_degradation_recente"]
].mean(axis=1)



# Récupérer les informations utiles des zones boisées
scores_zones_boisees = zones_boisees[
    cles + [
        "score_zones_boisees",
        "score_degradation_moyenne",
        "score_degradation_recente",
        "nombre_zones"
    ]
]


# Ajouter les informations aux données du bocage
score_bocage = score_bocage.merge(
    scores_zones_boisees,
    on=cles,
    how="left"
)




#############
# données natura 2000

biodiversite["departement"] = (
    biodiversite["departement"].astype(str).str.zfill(3)
)

biodiversite["id_cercle_ref"] = (
    biodiversite["id_cercle_ref"].astype("Int64")   # Int64 (avec la majuscule) est un type int acceptant les valeurs manquante
)

cles = ["departement", "id_cercle_ref"]
comparaison = score_bocage[cles].merge(
    biodiversite[cles],
    on=cles,
    how="left",
    indicator=True
)

# données natura 2000
colonnes_natura = [
    "departement",
    "id_cercle_ref",
    "nb_sites_natura",
    "part_natura_pct",
    "nb_habitats_distincts_sites_intersectes",
    "nb_habitats_prioritaires_distincts_sites_intersectes",
    "nb_taxons_cd_nom_species",
    "total_nb_influence_negative"
]

natura_carte = biodiversite[colonnes_natura].copy()



###########
# Calcul du score global
indicateurs_score = [
    "score_haies",
    "score_zones_boisees"
]


score_bocage["score_global"] = score_bocage[indicateurs_score].mean(axis=1)

# Calcul du score écologique estimé
score_bocage["score_ecologique"] = 100 - (
    score_bocage["score_densite"]
    + score_bocage["score_coherence"]
) / 2


###########################################################################################################################
# debut app


# Choix de l'indicateur à afficher
indicateurs = {
    #"Dernière analyse Linéaire de haies": "classe_lineaire",
    #"Dernière analyse Cohérence du réseau bocager": "classe_coherence",
    #"Evolution Linéaire de haies" : "evolution_classe_lineaire",
    #"Evolution Cohérence du réseau bocager" : "evolution_classe_coherence",
    "Priorité de restauration des haies": "score_haies",
    "Priorité de restauration des zones boisées": "score_zones_boisees",
    "Priorité de restauration du bocage": "score_global"
    }


indicateur_choisi = st.sidebar.selectbox(       #crée une liste déroulante dans la barre latérale de l'application
    "Indicateur à afficher",
    list(indicateurs.keys()),
    index=list(indicateurs.keys()).index(
        "Priorité de restauration du bocage"
    )
)


champ_classe = indicateurs[indicateur_choisi]  


if "departement_filtre" not in st.session_state:
    st.session_state.departement_filtre = "Tous"


# Données à afficher
donnee = score_bocage.copy()


if st.session_state.departement_filtre != "Tous":
    donnee = donnee[
        donnee["departement"] == st.session_state.departement_filtre
    ].copy()

donnee = donnee.merge(
    natura_carte,
    on=["departement", "id_cercle_ref"],
    how="left",
    validate="one_to_one"
)

# Classes disponibles (scores de 0 à 100, par tranches de 10)
classes_disponibles = list(range(10))



classes_selectionnees = st.sidebar.multiselect(     # propose une selection par classe
    "Classes à afficher",
    options=classes_disponibles,
    default=classes_disponibles
)


# Couleurs des classes
couleurs = {
    0: "#1a9850",
    1: "#66bd63",
    2: "#a6d96a",
    3: "#d9ef8b",
    4: "#ffffbf",
    5: "#fee08b",
    6: "#fdae61",
    7: "#f46d43",
    8: "#d73027",
    9: "#8b0000"
}


def style_cercle(feature):

    proprietes = feature["properties"]

    # Mise en évidence du cercle sélectionné
    if (
        id_selectionne is not None
        and str(proprietes.get("id_cercle_ref")) == str(id_selectionne)
        and str(proprietes.get("departement")) == str(departement_selectionne)
    ):
        return {
            "fillColor": "#00BFFF",
            "color": "#0033CC",
            "weight": 3,
            "fillOpacity": 0.9,
        }

    valeur = proprietes.get(champ_classe)

    try:
        valeur = float(valeur)
    except (TypeError, ValueError):
        valeur = None

    if valeur is None:
        classe = None

    elif champ_classe.startswith("score_"):
        classe = min(int(valeur // 10), 9)

    else:
        classe = int(valeur)

    return {
        "fillColor": couleurs.get(classe, "#808080"),
        "color": "#444444",
        "weight": 0.4,
        "fillOpacity": 0.7,
    }

    

# Application du filtre

if champ_classe.startswith("score_"):


    print(
        "Classes calculées :",
        sorted(
            donnee["score_global"].dropna()
            .apply(lambda x: min(int(x // 10), 9))
            .unique()
        )
    )

    classes = donnee["score_global"].apply(
        lambda x: min(int(x // 10), 9) if pd.notna(x) else None
    )

    masque = classes.isin(classes_selectionnees)

else:

    masque = donnee[champ_classe].isin(classes_selectionnees)

donnees_affichees = donnee[
    masque | donnee[champ_classe].isna()
].copy()






# Initialisation de la sélection
if "id_cercle_selectionne" not in st.session_state:
    premier_cercle = score_bocage.loc[
        score_bocage["score_global"].idxmax()
    ]

    st.session_state.id_cercle_selectionne = premier_cercle["id_cercle_ref"]
    st.session_state.departement_selectionne = premier_cercle["departement"]



id_selectionne = st.session_state.id_cercle_selectionne
departement_selectionne = st.session_state.departement_selectionne

# permet de séléctionner un cercle même lorsqu'un filtre est appliqué

donnees_carte = donnees_affichees.copy()

if id_selectionne is not None:

    cercle_selectionne = score_bocage[
        (score_bocage["id_cercle_ref"].astype(str) == str(id_selectionne))
        & (score_bocage["departement"].astype(str) == str(departement_selectionne))
    ]

    if not cercle_selectionne.empty:

        deja_present = (
            (donnees_carte["id_cercle_ref"].astype(str) == str(id_selectionne))
            & (donnees_carte["departement"].astype(str) == str(departement_selectionne))
        ).any()

        if not deja_present:
            donnees_carte = pd.concat(
                [donnees_carte, cercle_selectionne],
                ignore_index=True
            )






##########################################################################################################################
# Création de la carte
minx, miny, maxx, maxy = donnees_carte.total_bounds


carte = folium.Map(
    location=[(miny + maxy) / 2, (minx + maxx) / 2],
    zoom_start=8,
    tiles="OpenStreetMap"
)


# Informations affichées dans les infobulles

champs_infobulle = ["departement", "id_cercle_ref"]
aliases_infobulle = ["Département :", "Cercle :"]

if champ_classe == "score_global":

    champs_infobulle = ["score_global"] + champs_infobulle + [
        "score_haies",
        "score_zones_boisees"
    ]

    aliases_infobulle = ["Score global :"] + aliases_infobulle + [
        "Score des haies :",
        "Score des zones boisées :"
    ]

elif champ_classe == "score_haies":

    champs_infobulle = ["score_haies"] + champs_infobulle + [
        "score_densite",
        "score_coherence",
        "score_evolution_lineaire",
        "score_evolution_coherence"
    ]

    aliases_infobulle = ["Score des haies :"] + aliases_infobulle + [
        "Score densité :",
        "Score cohérence :",
        "Score évolution linéaire :",
        "Score évolution cohérence :"
    ]

elif champ_classe == "score_zones_boisees":

    champs_infobulle = ["score_zones_boisees"] + champs_infobulle + [
        "score_degradation_moyenne",
        "score_degradation_recente",
        "nombre_zones"
    ]

    aliases_infobulle = ["Score zones boisées :"] + aliases_infobulle + [
        "Score dégradation moyenne :",
        "Score dégradation récente :",
        "Nombre de zones boisées :"
    ]

else:

    champs_infobulle.append(champ_classe)
    aliases_infobulle.append("Valeur :")



# Informations complémentaires sur Natura 2000
champs_infobulle += [
    "nb_sites_natura",
    "part_natura_pct",
    "nb_habitats_distincts_sites_intersectes",
    "nb_habitats_prioritaires_distincts_sites_intersectes",
    "nb_taxons_cd_nom_species",
    "total_nb_influence_negative"
]

aliases_infobulle += [
    "Sites Natura 2000 :",
    "Surface couverte par Natura 2000 (%) :",
    "Habitats distincts recensés :",
    "Habitats prioritaires recensés :",
    "Taxons d'espèces recensés :",
    "Influences négatives recensées :"
]



# Affichage des cercles
folium.GeoJson(
    donnees_carte,
    style_function=style_cercle,
    tooltip=folium.GeoJsonTooltip(
        fields=champs_infobulle,
        aliases=aliases_infobulle
    )
).add_to(carte)



# Ajustement automatique du cadrage
if id_selectionne is not None and not cercle_selectionne.empty:

    minx, miny, maxx, maxy = cercle_selectionne.total_bounds
    carte.fit_bounds([[miny, minx], [maxy, maxx]])

else:
    carte.fit_bounds([[miny, minx], [maxy, maxx]])

# Titre de la carte

titre = "Priorité de restauration du bocage"
description = "Score global de priorité de restauration (0 à 100)"

st.markdown(f"### {titre}")

# Affichage de la carte
st_folium(
    carte,
    width=1200,
    height=650,
    use_container_width=True
)

# affichage de la phrase importante
st.markdown(
    "**Interprétation :** plus le score est élevé, plus la priorité "
    "de restauration écologique estimée est importante."
)

# Légende
st.markdown(f"**{description}**")

if indicateur_choisi == "Priorité de restauration du bocage":

    bornes = list(range(0, 101, 10))

    for classe, couleur in couleurs.items():
        debut = bornes[classe]
        fin = bornes[classe + 1]

        st.markdown(
            f'<span style="color:{couleur}">■</span> '
            f'Classe {classe} : {debut} à {fin}',
            unsafe_allow_html=True
        )

    st.markdown(
        '<span style="color:grey">■</span> Données indisponibles',
        unsafe_allow_html=True
    )





# affichage du classement


if champ_classe.startswith("score_"):

    st.markdown(f"### Classement des cercles : {indicateur_choisi}")

    # Sélection des cercles ayant un score disponible
    classement = donnee[
        donnee[champ_classe].notna()
    ].copy()

    # Tri selon le score sélectionné
    classement = classement.sort_values(
        by=champ_classe,
        ascending=False
    )

    classement.insert(
        0,
        "Rang",
        range(1, len(classement) + 1)
    )

    # Colonnes communes
    colonnes = [
        "Rang",
        "departement",
        "id_cercle_ref",
        champ_classe
    ]

    # Colonnes complémentaires selon le score choisi
    if champ_classe == "score_global":

        colonnes += [
            "score_haies",
            "score_zones_boisees"
        ]

    elif champ_classe == "score_haies":

        colonnes += [
            "score_densite",
            "score_coherence",
            "score_evolution_lineaire",
            "score_evolution_coherence"
        ]

    elif champ_classe == "score_zones_boisees":

        colonnes += [
            "score_degradation_moyenne",
            "score_degradation_recente",
            "nombre_zones"
        ]

    colonnes += [
    "nb_sites_natura",
    "part_natura_pct",
    "nb_habitats_distincts_sites_intersectes",
    "nb_habitats_prioritaires_distincts_sites_intersectes",
    "nb_taxons_cd_nom_species",
    "total_nb_influence_negative"
]

    # Filtres
    col1, col2 = st.columns(2)

    with col1:
        departements = ["Tous"] + sorted(
            classement["departement"].dropna().unique().tolist()
        )

        departements = ["Tous"] + sorted(
            score_bocage["departement"].dropna().unique().tolist()
        )

        departement_choisi = st.selectbox(
            "Département",
            departements,
            key="departement_filtre"
        )

    with col2:
        recherche = st.text_input(
            "Rechercher un cercle (identifiant)"
        )

    # Application des filtres
    if departement_choisi != "Tous":
        classement = classement[
            classement["departement"] == departement_choisi
        ]

    if recherche:
        classement = classement[
            classement["id_cercle_ref"].astype(str).str.contains(
                recherche,
                case=False
            )
        ]

    # Affichage du tableau
    evenement = st.dataframe(
        classement[colonnes],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tableau_classement"
    )

    # Gestion de la sélection d'un cercle
    if evenement.selection.rows:
        index_selectionne = evenement.selection.rows[0]
        cercle = classement.iloc[index_selectionne]
        nouvel_id = cercle["id_cercle_ref"]
        nouveau_departement = cercle["departement"]

        st.session_state.id_cercle_selectionne = nouvel_id
        st.session_state.departement_selectionne = nouveau_departement
        st.rerun()


