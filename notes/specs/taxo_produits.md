# Taxonomie des produits Stripe (metadata des produits)

   - les champs `domain`, `family`, `genre`, `offer` devraient suffire à identifier un produit unique.
   - le champ `reference` doit être unique.
   - le champs `maximum` n'est utilisé que pour les BW avec seuils de clients.
   - les champs `Subs` et `article` sont obsolètes. Ils ne sont plus censés être utilisés par l'application. Seule la taxonomie (`domain`, `family`, `genre`, `offer`) et les champs `reference`, `maximum` sont lus.


| domain       | family          | genre   | offer | maximum | reference                           | Subs         | article                            |
|--------------|-----------------|---------|-------|---------|-------------------------------------|--------------|------------------------------------|
| bw           | academics       | any     | free  |         | BW4AC                               | BW4AC        |                                    |
| bw           | leaders_experts | GE      | paid  | 9999999 | BW4L&E\-GE                          | BW4L&E\-GE   |                                    |
| bw           | leaders_experts | ETI     | paid  |     999 | BW4L&E\-ETI                         | BW4L&E\-ETI  |                                    |
| bw           | leaders_experts | PME     | paid  |     249 | BW4L&E\-PME                         | BW4L&E\-PME  |                                    |
| bw           | leaders_experts | solo    | paid  |       9 | BW4L&E\-Solo                        | BW4L&E\-Solo |                                    |
| bw           | leaders_experts | TPE     | paid  |      49 | BW4L&E\-TPE                         | BW4L&E\-TPE  |                                    |
| bw           | media           | any     | free  |         | BW4Media                            | BW4Media     |                                    |
| bw           | pr              | any     | paid  |         | BW4PR                               | BW4PR        |                                    |
| bw           | transformers    | ETI     | paid  |     999 | BW4T\-ETI                           | BW4T\-ETI    |                                    |
| bw           | transformers    | GE      | paid  | 9999999 | BW4T\-GE                            | BW4T\-GE     |                                    |
| bw           | transformers    | PME     | paid  |     249 | BW4T\-PME                           | BW4T\-PME    |                                    |
| bw           | transformers    | solo    | paid  |       9 | BW4T\-Solo                          | BW4T\-Solo   |                                    |
| bw           | transformers    | TPE     | paid  |      49 | BW4T\-TPE                           | BW4T\-TPE    |                                    |
| license      | article         | news    | paid  |         | article\-licence\-news              |              | article\-licence\-news             |
| license      | article         | feature | paid  |         | article: article\-licence\-feature  |              | article: article\-licence\-feature |
| license      | article         | survey  | paid  |         | article\-licence\-survey            |              | article\-licence\-survey           |
| license      | article         | exclu   | paid  |         | article\-licence\-exclu             |              | article\-licence\-exclu            |
| license      | article         | itw     | paid  |         | article\-licence\-itw               |              | article\-licence\-itw              |
| license      | article         | report  | paid  |         | article\-licence\-report            |              | article\-licence\-report           |
| consultation | article         | news    | free  |         | c\-article\-o\-news                 |              | c\-article\-o\-news                |
| consultation | article         | dossier | free  |         | c\-article\-o\-dossier              |              | c\-article\-o\-dossier             |
| consultation | article         | survey  | free  |         | c\-article\-o\-surv                 |              | c\-article\-o\-surv                |
| consultation | article         | exclu   | free  |         | c\-article\-o\-exclu                |              | c\-article\-o\-exclu               |
| consultation | article         | itw     | free  |         | c\-article\-o\-itw                  |              | c\-article\-o\-itw                 |
| consultation | article         | report  | free  |         | c\-article\-o\-reportage            |              | c\-article\-o\-reportage           |
| consultation | article         | news    | paid  |         | c\-article\-news                    |              | c\-article\-news                   |
| consultation | article         | dossier | paid  |         | c\-article\-dossier                 |              | c\-article\-dossier                |
| consultation | article         | survey  | paid  |         | c\-article\-surv                    |              | c\-article\-surv                   |
| consultation | article         | exclu   | paid  |         | c\-article\-exclu                   |              | c\-article\-exclu                  |
| consultation | article         | itw     | paid  |         | c\-article\-itw                     |              | c\-article\-itw                    |
| consultation | article         | report  | paid  |         | c\-article\-reportage               |              | c\-article\-reportage              |
| certificate  | article         | news    | paid  |         | certificate\-news                   |              | certificate\-news                  |
| certificate  | article         | feature | paid  |         | certificate\-feature                |              | certificate\-feature               |
| certificate  | article         | survey  | paid  |         | certificate\-survey                 |              | certificate\-survey                |
| certificate  | article         | exclu   | paid  |         | certificate\-exclusive              |              | certificate\-exclusive             |
| certificate  | article         | itw     | paid  |         | certificate\-interview              |              | certificate\-interview             |
| certificate  | article         | report  | paid  |         | certificate\-report                 |              | certificate\-report                |
