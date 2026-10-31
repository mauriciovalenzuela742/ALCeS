# Revisión bibliográfica: curvas de luz como imágenes para clasificar transientes

Primera pasada: 2026-10-20. Segunda pasada (citas hacia adelante, texto completo y NASA
ADS): 2026-10-31. Es la Parte 1 del plan "Opción A". Las referencias están en `refs.bib`.

## Estado de esta revisión (léase primero)
- **Herramientas:** buscador web general, abstracts y HTML de arXiv, API de Semantic Scholar
  y, desde el 2026-10-31, la API de NASA ADS (registro abajo).
- **Origen de las BibTeX:** ninguna se escribió a mano. De las 42 entradas de `refs.bib`, 33
  vienen de la exportación de ADS (28 reemplazaron a su `@misc` de arXiv conservando la clave
  de cita, y 5 son nuevas con la clave = bibcode). Las otras 9 siguen como `@misc` de
  `arxiv.org/bibtex` porque ADS no tiene versión con revista, o porque se cita una versión de
  arXiv distinta de la publicada (2305.13745, con una nota en la entrada). ATAT quedó como
  A&A 689, A289 (la referencia A&A 691, A163 de la primera pasada no corresponde).
- **ID 2305.13745, resuelto:** en la primera pasada lo descarté porque su título actual es
  "LightCurve MoE". Pero su v1 (mayo 2023) es justamente el estudio de Kepler: "Transfer
  Learning Applied to Stellar Light Curve Classification" (Wang+23), con wavelets, GAF y
  *recurrence plots*. La v3 (julio 2025) cambió el título y el método. Volvió a `refs.bib`.
- **Fichas:** salen de abstracts y resúmenes, salvo las leídas en texto completo:
  Moreno-Cartagena et al. (2025a), y el 2026-10-31 ORACLE, Biswas+23, El-CID, Liang+23 y
  Alves+23 (ver "Lectura en texto completo"). En las demás, las cifras se tienen que confirmar
  en el PDF antes de usarlas.

## Registro de búsquedas (2026-10-20)
| # | Cadena (buscador web) | Hallazgos relevantes |
|---|---|---|
| 1 | SCONE supernova CNN Gaussian process heatmaps | SCONE (2106.04370), SCONE temprano (2111.05539) |
| 2 | light curve image representation CNN transient LSST sparse early | Mahabal+17 (dm-dt), NEEDLE, embeddings multibanda |
| 3 | kilonova photometric classification ML LSST | TLW, El-CID, revisiones generales |
| 4 | Gramian angular field / recurrence plot astronomical CNN | Wang & Oates 2015, Hatami+17, estudio de Kepler (sin verificar) |
| 5 | ATAT ALeRCE transformer | ATAT (2405.03078), ATCAT (2511.00614, sin revisión por pares) |
| 6 | ELAsTiCC classification results brokers | Fink benchmarks, AMPEL, MALLORN, clasificador de TDE |
| 7 | 2D heatmap CNN vs RNN/transformer pocas observaciones | Brunel+19 (CNN 1D vs LSTM), modelos de atención |
| 8 | Mahabal 2017 dm-dt | 1709.06257 |
| 9 | KN Kasen vs Bulla sistemáticas del clasificador | El-CID, WFST (2312.12169), 7DT |
| 10 | stamp classifier y LC classifier de ALeRCE | 2008.03309, 2008.03311, extensión TDE 2503.19698 |
| 11 | RAPID, SuperNNova, ParSNIP, Avocado | 1904.00014, 1901.06384, 2109.13999, 1907.04690 |
| 12 | fuga de información por templates en train/test | **nada encontrado** |
| 13 | vision transformer preentrenado y curvas de luz como imagen | **Moreno-Cartagena+25 (2502.20479, 2507.11711)** |
| 14 | Fink kilonova | Biswas+23 (2210.17433) |
| 15 | PLAsTiCC modelos y resultados | Kessler+19, Hložek+23 |
| 16 | efecto de la cadencia de LSST en la clasificación | Alves+22, Alves+23 |

**Segunda pasada (2026-10-31).** Citas hacia adelante desde la API de Semantic Scholar (sin
llave), filtradas por título y leídas en el abstract de arXiv:

| Semilla | Citas | Relevantes |
|---|---|---|
| SCONE (2106.04370) | 39 | ORACLE (2501.01496); el resto es cosmología con SN Ia, otros surveys o espectros |
| SCONE temprano (2111.05539) | 17 | WFST SSVAE (2506.01216), PIE-ADA (2606.29367), NEEDLE, TLW |
| Moreno-Cartagena+25a (2502.20479) | 6 | AppleCiDEr (2507.16088), Moreno-Cartagena+25b, revisión de Rehemtulla+25 (2512.11959) |
| Biswas+23 (2210.17433) | 10 | KilonovaSCORER (2604.22994), Stevenson+25 (2510.12932), Plestkova+25 (2507.11785) |

Búsquedas web de esta pasada:

| # | Cadena | Hallazgos |
|---|---|---|
| 17 | Kepler GAF / recurrence plot / MTF CNN | Wang+23 (= v1 de 2305.13745), Choudhary+25 (2506.16597), Donnelly & Dutta (AAAI 2024, sin arXiv) |
| 18 | clasificador de TDE Rubin ELAsTiCC2 A&A 2025 | Bhardwaj+25 (2509.25902, A&A 703, A95) |
| 19 | paper de resultados de ELAsTiCC | **no existe** (ver abajo); sí NAPTIME (2607.19236) y "Beyond the Final Label" (2604.23792) |

**Registro en NASA ADS (2026-10-31).** Cadenas en la sintaxis de ADS sobre título, abstract
y palabras clave (`abs:`), con filtro `year:2015-2026 collection:astronomy`. Se revisaron los
25 primeros por relevancia que no estaban en `refs.bib`. Las cadenas exactas están en
`scripts/ads_search.py` (y el reemplazo de BibTeX en `scripts/ads_bib.py`).

| # | Tema (cadena `abs:`) | Resultados | Nuevo y relevante |
|---|---|---|---|
| 1 | GP + heatmap o CNN + supernova + clasificación | 4 | Qu 2022 (taller ML4Astro, 2207.09440) |
| 2 | curva de luz + imagen o 2D + CNN o ViT + transiente + clasificación | 17 | Bugueño+21 (MTF) |
| 3 | kilonova + clasificación + LSST/Rubin/ZTF + fotométrica | 25 | — (sobre todo GCN y búsquedas de contrapartes) |
| 4 | GAF / recurrence plot / MTF + curva de luz | 20 | Bugueño+21; Pagliaro+26 |
| 5 | ALeRCE + transformer | 2 | — |
| 6 | ELAsTiCC | 26 | Solo resúmenes de AAS 241 (no hay paper de resultados) |
| 7 | (transformer o RNN) + CNN + curva de luz + clasificación | 5 | — |
| 8 | dm-dt + curva de luz | 14 | — (binarias) |
| 9 | kilonova + (Kasen o Bulla) + clasificación | **0** | — |
| 10 | ALeRCE + clasificador | 93 | — |
| 12 | fuga (*leakage*) + template o simulación + clasificación | **2** | — (ninguno de transientes) |
| 13 | vision transformer + curva de luz | 7 | — |
| 14 | Fink + kilonova | 17 | — |
| 15 | PLAsTiCC + clasificación | 46 | — |
| 16 | cadencia + LSST + clasificación fotométrica | 12 | — |
| 20 | clasificación temprana + transiente + LSST/ZTF/Rubin | 12 | Lin+26 |
| 21 | kilonova + distinguir o comparar modelos + curva de luz + LSST | 5 | — |
| 22 | escasa o pocas épocas + curva de luz + clasificación + LSST | 19 | — |

Citas hacia adelante en ADS (más completas que Semantic Scholar): SCONE 71, SCONE temprano
29, Moreno-Cartagena+25a 10 y Biswas+23 16. Lo nuevo y relevante es Gupta+25 (transferencia
de simulaciones a datos reales y de ZTF a LSST); ConvEntion (Bairouk+23) usa series de
stamps, que es la opción B.

## Fichas
| Trabajo | Representación | Modelo | Datos | ¿KN? | ¿Pocas épocas? | Resultado clave | Qué deja abierto |
|---|---|---|---|---|---|---|---|
| **SCONE**, Qu+21 | Imagen: GP 2D (tiempo × λ), canales de flujo e incertidumbre | CNN | PLAsTiCC | No (solo SN) | No | 98.2% en 6 tipos de SN | Rendimiento fuera de distribución menor |
| **SCONE temprano**, Qu & Sako 22 (AJ, doi:10.3847/1538-3881/ac39a1) | Igual a SCONE, truncado a 0, 5, 15, 25 y 50 días del trigger | CNN | LSST simulado | No | **Sí**, por días | 75 % en el trigger y 89 % a 50 días con z (60 % y 82 % sin z) | Sin KN; corta por días, no por número de noches detectadas |
| **Moreno-Cartagena+25a** (ALeRCE / U. de Concepción) | Imagen: gráfico matplotlib 256×256 (grilla o superpuesto) | SwinV2 preentrenado | ELAsTiCC (20 clases), MACHO | No se mencionan | **No** | F1 macro 65.5 en ELAsTiCC (ATAT 64.2 sin metadatos) | Subclases de SN difíciles; sin metadatos; sin evaluación temprana; no agrupa por template |
| Moreno-Cartagena+25b | Imagen, ViT en dos ramas | SwinV2 | ZTF + ATLAS reales | — | No | Combinar surveys mejora | Taller ICML-ML4Astro |
| Mahabal+17 | Imagen dm-dt | CNN | CRTS (periódicas) | No | — | Las curvas escasas quedan sin clasificar | Ya identifica la escasez como modo de falla |
| **ATAT**, Cabrera-Vives+24 | Secuencia + tabular | Transformer | ELAsTiCC (20 clases) | ELAsTiCC sí incluye KN | — | F1 macro 82.9 con metadatos | Es la línea base natural de ALeRCE |
| **RAPID**, Muthukrishna+19 | Secuencia | GRU | PLAsTiCC/ZTF simulado | Sí | **Sí**, clasifica en cada época | — | No compara con imágenes |
| SuperNNova, Möller+20 | Secuencia | RNN bayesiana | SNANA | Adaptable | Parcial | — | — |
| Avocado, Boone 19 | Features + aumentación con GP | GBDT | PLAsTiCC | Sí | — | Ganó PLAsTiCC | — |
| ParSNIP, Boone 21 | Latente físico | VAE + clasificador | PLAsTiCC, PS1 | Sí | — | 2-2.3x menos contaminación de SN Ia | — |
| Brunel+19 | CNN 1D vs LSTM | — | SN simuladas | No | — | — | Única comparación directa CNN vs RNN encontrada |
| **Biswas+23** (KN en Fink) | PCA + random forest | RF | Simulaciones tipo ZTF | **Sí**, binaria (KN vs resto) | **Sí**, ventana de 30 días | 69.3 % de precisión y 69.7 % de recall (simulado) | Usa features, no imágenes; partición aleatoria |
| **Liang+23** (WFST) | Curva interpolada | Red neuronal | Bulla + MOSFiT, contra 6 tipos de SN | **Sí**, binaria | Sí, 3 días tras el trigger | Exactitud 98.4 %; precisión 94.8 % y recall 94.1 % | No separa modelos de KN; partición aleatoria 70/30 |
| **El-CID**, Chatterjee+21 | Curva interpolada a 12 pasos en 10 días | Red chica (~13 000 parámetros) | Bulla + Kasen | **Sí**, binaria | Sí, ~3 días | ≥99 % de exactitud a ~3 días | La prueba de que no aprende la cadencia usa una sola cadencia (minion_1016) |
| **Alves+22, Alves+23** | Features (snmachine: wavelets de un GP 2D + PCA) | LightGBM | PLAsTiCC / baseline_v2.0 y variantes | No | No evalúa clasificación temprana, pero **estratifica por muestreo** (largo, huecos, observaciones cerca del pico) | En rolling, la región activa tiene ~25 % mejor log-loss que la de fondo, pero el rolling mejora poco en total; 3 visitas por noche empeora ~10 % | Un solo clasificador; no evalúa imágenes |
| Hložek+23, Kessler+19 | Desafío PLAsTiCC | — | — | Sí | — | Los mejores clasifican bien SN Ia y KN | — |
| Carrasco-Davis+21 | Stamps de píxeles | CNN | ZTF real | — | 1ª detección | ~94% (5 clases amplias) | Es la opción B, fuera de alcance |
| Sánchez-Sáez+21, Pavez-Herrera+25 | Features | BHRF | ZTF real | No | — | Clasificador LC de ALeRCE (+TDE) | — |
| Fraga+24 (Fink), MALLORN 25, NEEDLE 23, ATCAT 25 | Varias | — | ELAsTiCC / real | Varía | — | Contexto de brokers | ATCAT sin revisión por pares |
| Wang & Oates 15, Hatami+17 | GAF, *recurrence plot* | CNN | Series genéricas | — | — | Origen de las codificaciones como imagen | — |
| **ORACLE**, Shah+25 (ApJ 995, 4) | Secuencia + contexto del host | GRU jerárquica | ELAsTiCC (19 clases) | **Sí** | **Sí, por días** desde la 1ª detección (1 a 1024) | Precisión macro 0.96 en transiente vs variable con 1 día; 0.83 en 19 clases a 1024 días | Sin imágenes; corta por días, no por noches detectadas; sin partición por template |
| Zhou+26, "Beyond the Final Label" (ApJ 1006, 223) | Historias de clasificación de los brokers | RNN + atención | ELAsTiCC | Sí | Propone métricas de estabilidad y clasificación temprana | Mejora sobre los clasificadores del desafío | Métricas de interés para nuestro protocolo |
| NAPTIME, Earl+26 | Secuencia, *neural process* | — | ELAsTiCC2, MALLORN | — | Parcial: 10 % inicial de las medidas | F1 macro 0.874 sin metadatos; ~0.34 con el 10 % inicial | Corta por fracción de medidas, no por noches |
| WFST SSVAE, Tang+25 (AJ 169, 304) | Secuencia | VAE semisupervisado | WFST simulado | — | **Sí**, 3 días tras el trigger | +5.6 % de exactitud sobre RNN | Sin imágenes |
| AppleCiDEr, Junell+25 | Fotometría + stamps + metadatos + espectros | Transformers + CNN | ~30 000 alertas reales de ZTF | — | Clasificación temprana | Marco multimodal | Las imágenes son stamps (opción B), no la curva |
| Bhardwaj+25 (A&A 703, A95) | Features de GP | XGBoost | ELAsTiCC2 | — | No | TDE: precisión 95 %, recall 72 % | Es el "clasificador de TDE para Rubin" del pendiente 4 |
| KilonovaSCORER, Darc & Kilpatrick 26 | Consistencia con una grilla de KN | ABC | Simulaciones LSST ToO | **Sí** | **Sí**, días tras el trigger GW | Descarta SN en 3-4 días | KN vs SN; no separa modelos de KN |
| Wang+23 (v1 de 2305.13745) | Imagen: wavelet, GAF, *recurrence plot* | 6 CNN (VGG-19 la mejor) | Kepler (variables) | No | No | Wavelet la mejor (95.6 %) | Es el estudio de Kepler buscado; series densas, no escasas |
| Choudhary+25 (2506.16597) | GAF y *recurrence plot* | ViT | Kepler (tránsitos) | No | No | RP mejor que GAF | Series densas |
| **Lin+26** (Universe 12, 268) | Features vs secuencia | XGBoost, LSTM, Transformer | ~1.7 M segmentos reales de ZTF y ATLAS, 7 clases | No | **Sí, por número de observaciones (3 a 30)** | Transformer preentrenado 0.946; >90 % con 7 observaciones; sin preentrenar 0.513 | Sin imágenes; datos reales, no simulaciones con template |
| **Qu 2022** (taller ML4Astro, 2207.09440) | Imagen GP (SCONE) | CNN | SN simuladas | No | **Sí, por noches** | 60 % en 6 tipos de SN con 2 noches; 98 % con la curva completa | Imagen por noches, pero sin comparar con secuencias ni features |
| Bugueño+21 (A&C 35, 100461) | Imagen MTF de 2 canales para muestreo irregular | CNN | Kepler (tránsitos) | No | No | Competitivo y más simple | Codificación pensada para muestreo irregular |
| Pagliaro+26 (A&A 714, A146) | Features, curva cruda, imagen GAF | 9 clasificadores (incluye CNN2D sobre GAF) | PLAsTiCC | Sí (PLAsTiCC) | No | *Benchmark* de explicabilidad, 5 semillas | Compara representaciones, pero para explicabilidad, no exactitud con pocas noches |
| Gupta+25 (MNRAS 542, L132) | Secuencia | Transferencia de aprendizaje | ZTF simulado → real; ZTF → LSST | — | No | 95 % menos etiquetas reales | Brecha simulación-realidad; relevante para entrenar con ALCeS |

## Hueco identificado

**1. La idea de "curva de luz como imagen + CNN o ViT" ya está publicada.** Existe con
imágenes GP (SCONE) y con gráficos y SwinV2 preentrenado (Moreno-Cartagena+25a). Este segundo
trabajo es del **mismo entorno ALeRCE** (Cabrera-Vives, U. de Concepción). Por eso, plantear
la pregunta original como "¿sirven las imágenes?" **no es nuevo**. Antes de seguir, el
profesor tiene que saberlo y conviene coordinarse o colaborar con ese grupo.

**2. Lo que no encontré.** Esto es ausencia en dos pasadas (búsqueda web, citas hacia
adelante y NASA ADS), no prueba de que no exista. Los cuatro huecos siguen abiertos, pero (a)
queda acotado:
- Qu 2022 ya evalúa una imagen GP **por noches** (60 % con 2 noches), y Lin+26 compara
  features y secuencias **por número de observaciones** (3 a 30) en datos reales.
- Lo que nadie hace es la comparación **controlada** imagen vs secuencia vs features, con los
  mismos objetos y estratificada por noches con detección. Ese es el aporte de (a).
- En ADS, "kilonova + (Kasen o Bulla) + clasificación" da **0** resultados y "fuga +
  template + clasificación" no da ninguno de transientes: refuerza (b) y (c).
- **(a) Imagen vs secuencia en el régimen de pocas noches.** No hay comparación controlada
  estratificada por **número de noches con detección**. SCONE trunca por días y
  Moreno-Cartagena+25a no evalúa curvas tempranas.
- **(b) Fuga de información por template.** No encontré ningún trabajo que agrupe la
  partición train/test por template SIMSED. Con la grilla de KN, el mismo template puede
  aparecer en train y test, lo que inflaría la exactitud.
- **(c) Distinguir entre *modelos* de KN** (K17 vs BULLA19), no solo KN vs resto. Los trabajos
  de KN usan varios modelos (El-CID, WFST), pero clasifican KN contra contaminantes. Cuánta
  información sobre el modelo físico sobrevive al muestreo de LSST parece no estar
  estudiado. Nuestro diagnóstico ya tiene una primera respuesta: 1.0 en templates y 0.57 con
  1 noche.
- **(d) Efecto de la versión de OpSim** (v5.0 vs v5.3) en clasificadores basados en imagen.
  Alves+22 y Alves+23 lo estudian solo con features.

**3. Pregunta reformulada (propuesta para el profesor):**
> ¿Cuánta información de clase sobrevive al muestreo escaso de LSST, y depende de la
> representación? Se comparan imagen (GP 2D y gráfico estilo SwinV2), secuencia y features
> según el número de noches detectadas, con particiones agrupadas por template para evitar
> fuga. El caso límite son dos modelos de KN, K17 y BULLA19.

Lo que aportaría:
- un protocolo de evaluación (estratificado por noches y agrupado por template), aplicable a
  cualquier clasificador, incluidos los de ALeRCE;
- un resultado sobre separabilidad de modelos de KN;
- simulaciones ALCeS validadas contra SNANA (motor LCL).

El "uso de GPU" deja de ser la pregunta y pasa a ser el medio.

**4. Implicaciones para el experimento (Parte 2 del plan):**
- Agregar la representación de Moreno-Cartagena+25a (gráfico + SwinV2 preentrenado) como
  segunda variante de imagen. El SwinV2 preentrenado cabe en una V100.
- Usar ATAT como línea base de secuencia en vez de una GRU propia, si su código
  (`alercebroker/ATAT`) corre sobre nuestros datos.
- Medir (b) primero, porque es barato: el mismo modelo con partición aleatoria vs agrupada
  por `TEMPLATE_INDEX`. Si la diferencia es grande, ese resultado vale por sí solo.

**Lectura en texto completo (2026-10-31).** Tres preguntas en cada trabajo: cómo trunca,
cómo particiona y cómo trata los modelos de KN.

| Trabajo | Truncamiento | Partición train/test | Modelos de KN |
|---|---|---|---|
| ORACLE (Shah+25) | Entrena con una fracción aleatoria de las observaciones; prueba por días desde el trigger (1 a 1024) | 70/30 sin decir si es aleatoria o agrupada; no menciona templates | **KN_K17 y KN_B19 juntos en una clase "KN"** |
| Biswas+23 | Ventana de 30 días | **Aleatoria** | Binaria (KN vs resto); mezcla Kasen y otras simulaciones |
| El-CID (Chatterjee+21) | 10 días desde el trigger | 60/40 sin decir cómo | **BU19 y KN17 juntos**; solo reporta que la detección no prefiere un modelo |
| Liang+23 | 3 días desde el trigger | **Aleatoria** 70/30 | **Bulla y MOSFiT juntos** |
| Alves+23 | No trunca | No la describe | Sin KN |

Esto **refuerza los huecos (b) y (c)**:
- Ningún trabajo agrupa la partición por template, y dos dicen explícitamente que es
  aleatoria.
- Todos los que incluyen KN juntan los modelos en una sola clase: nadie pregunta si se
  distinguen.

Para (a), ninguno corta por número de noches con detección; el más cercano en espíritu es
Alves+23, que estratifica por propiedades del muestreo, pero solo con features y curvas
completas.

**Cifras corregidas respecto de la primera pasada:**
- Alves+23: el "+25 %" no es del rolling en general, sino de la región activa contra la de
  fondo.
- Liang+23: los contaminantes son 6 tipos de SN, no solo Ia.
- ORACLE: el abstract da 0.96 de precisión macro (transiente vs variable) "a 1 día", pero la
  tabla 5 la da a 2 días.
- Liang+23 se contradice: la sección 3.2 y la 5 dan con las clases invertidas el ≳98 % y
  ≳92 % por clase.

**5. ELAsTiCC no tiene paper oficial de resultados.** El portal de DESC
(portal.nersc.gov/cfs/lsst/DESC_TD_PUBLIC/ELASTICC) solo enlaza dos pósters (AAS enero 2023 y
Cosmic Streams diciembre 2023). Los trabajos lo citan como "Knop & ELAsTiCC Team 2023" o
"Narayan & ELAsTiCC Team 2023", y el *white paper* de IA/ML de DESC (2601.14235) describe la
infraestructura, no la exactitud. Si usamos ELAsTiCC como referencia, hay que citar los
pósters o el portal.

## Pendientes de esta revisión
1. ~~Repetir las cadenas en ADS~~ (hecho 2026-10-31).
2. ~~Citas hacia adelante de SCONE, Moreno-Cartagena+25a y Biswas+23~~ (hecho 2026-10-31, en
   Semantic Scholar y en ADS).
3. ~~Leer en texto completo Biswas+23, El-CID, Liang+23, Alves+23 y ORACLE~~ (hecho
   2026-10-31). Revistas confirmadas en ADS: Biswas+23 (A&A 677, A77), El-CID (MNRAS 509,
   914) y Liang+23 (Universe 10, 10). Falta el texto completo de SCONE temprano y de Qu 2022.
4. ~~Estudio de Kepler y clasificador de TDE~~ (hecho: Wang+23 y Bhardwaj+25).
5. ~~Paper de resultados de ELAsTiCC~~ (no existe).
6. ~~Reemplazar las entradas `@misc` por las de revista desde ADS~~ (hecho 2026-10-31).
   KilonovaSCORER figura en ADS publicado en PASP 138, 084502, pero su registro de arXiv aún
   no está unido al de la revista: actualizarlo más adelante.
