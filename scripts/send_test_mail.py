from devtools import debug

from app.flask.extensions import mail
from app.flask.main import create_app

SUBJECT = "Email from Python"
BODY = """
Pour cette nouvelle année qui démarre, je vous adresse mes meilleurs vœux. Et parmi ceux-ci, que nous devenions acteurs du changement dont l'Europe a besoin.

Nous ne pouvons plus nous contenter de rêver d'un futur numérique plus libre et plus juste. Nous devons agir, pour aider l'Europe à prendre son destin numérique en main, à s'affranchir de ses dépendances et à construire un écosystème numérique basé sur l'ouverture, la transparence et la collaboration.

1. La souveraineté numérique, c'est maintenant.

Avec le projet Hop3, que nous avons pu présenter en décembre dernier à l'OSXP, et qui vient de bénéficier de deux financements européens, nous passons à l'action.

Hop3 simplifie le déploiement d'applications et permet à chacun, entreprises comme particuliers, de reprendre le contrôle de son infrastructure IT, en toute sécurité et sans dépendance aux géants du web. Hop3, c'est la liberté retrouvée !

2. L'Initiative EuroStack : bâtir un écosystème numérique européen fort.

Il est temps de fédérer les forces vives du numérique ouvert et souverain en Europe. Nous avons lancé ces dernières semaines l'Initiative EuroStack, avec pour ambition de créer un cercle vertueux d'innovation et de collaboration.

Ses objectifs clés :

    Le répertoire EuroStack (ESDP) : Une plateforme unique pour découvrir et adopter les solutions et les technologies numériques européennes. Finie la jungle des solutions propriétaires, place à la transparence et à l'interopérabilité !
    Favoriser la collaboration et l'investissement: EuroStack encourage le partage de connaissances, le développement conjoint et l'investissement dans des projets stratégiques. Ensemble, nous sommes plus forts !
    Promouvoir l'adoption (et, de fait, le financement) de l'Open Source par les administrations et les entreprises.

3. 2025 : L'année de l'engagement et de l'action.

Les outils existent, nous proposons la vision, il est temps de passer à la vitesse supérieure.

Notre appel à l'action :

    Adoptez et utilisez les solutions et technologies open source européennes, comme Hop3. "La preuve est dans le pudding", comme l'écrivait Agatha Christie ! Démontrons ensemble la vitalité de l'écosystème numérique européen !
    Relayez l'Initiative EuroStack et participez à la construction d'un écosystème Open Source européen florissant.
    Interpellez vos décideurs. Exigez qu'ils soutiennent et adoptent des solutions Open Source.

En 2025, relevons la tête, dépassons les discours résignés et faisons de l'Europe un leader de l'Open Source, un modèle de souveraineté numérique et d'innovation ouverte. L'avenir est entre nos mains. Ensemble, construisons un futur numérique où la liberté, la transparence et la collaboration sont les maîtres mots.

Bonne année 2025, une année décisive pour l'Open Source et pour l'Europe !

Stefane Fermigier
Fondateur & Président, Abilian
Founder, EuroStack Initiative et EuroStack Directory Projecte
"""
RECIPIENTS = [
    "sf@fermigier.com",
    "sfermigier@gmail.com",
]


def send():
    app = create_app()
    with app.app_context():
        result = mail.send_mail(
            subject=SUBJECT,
            recipient_list=RECIPIENTS,
            message=BODY,
        )
        debug(result)


if __name__ == "__main__":
    send()
