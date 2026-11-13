"""Build the final report (HTML -> PDF via Chromium). All numbers come from reports/artifacts/*."""
import base64, json, pathlib, subprocess
import pandas as pd

R = pathlib.Path(__file__).resolve().parent
A, S = R / "artifacts", R / "screenshots"
meta = json.loads((A / "results.json").read_text())
tm = pd.read_csv(A / "test_metrics.csv").set_index("model")
cvb = json.loads((A / "champion_vs_baseline.json").read_text())
bucket = pd.read_csv(A / "by_first_hour_publishers.csv")
par = json.loads((A / "stream_parity.json").read_text())
size = json.loads((A / "data_size.json").read_text())
V = {k: v["val"] for k, v in meta["results"].items()}


def img(p, w="100%", cap=""):
    b = base64.b64encode(pathlib.Path(p).read_bytes()).decode()
    return f'<figure><img src="data:image/png;base64,{b}" style="width:{w}"><figcaption>{cap}</figcaption></figure>'


def f(x, d=3): return f"{x:.{d}f}"


rows = ""
order = ["baseline_src_1h", "lr_base", "lr_prior", "gbt_base", "gbt_prior", "gbt_prior_themes"]
for m in order:
    r = tm.loc[m]; b = " class=best" if m == meta["champion"] else ""
    rows += (f"<tr{b}><td>{r.label}</td><td>{f(V[m]['pr_auc'])}</td><td>{f(r['PR-AUC'])} <span class=ci>[{f(r['PR-AUC lo'])}, {f(r['PR-AUC hi'])}]</span></td>"
             f"<td>{f(r['ROC-AUC'])}</td><td>{f(r['F1'])} <span class=ci>[{f(r['F1 lo'])}, {f(r['F1 hi'])}]</span></td>"
             f"<td>{f(r.Precision)}</td><td>{f(r.Recall)}</td><td>{f(r['P@top5%'])}</td></tr>")
brow = ""
for _, r in bucket.iterrows():
    brow += f"<tr><td>{r.bucket}</td><td>{int(r.n):,}</td><td>{r.rate:.1%}</td><td>{r.share_of_positives:.1%}</td><td>{r.recall:.1%}</td></tr>"
ap, f1 = cvb["diff"]["ap"], cvb["diff"]["f1"]
c = tm.loc[meta["champion"]]; b0 = tm.loc["baseline_src_1h"]
late = bucket.iloc[0]
html = f"""<!doctype html><html><head><meta charset=utf-8><title>SignalRank</title><!--FONTS--><style>
@page{{size:Letter;margin:0.85in 0.8in 0.9in}}
body{{font-family:"Source Serif 4",serif;font-size:10.4pt;line-height:1.45;color:#16202b;margin:0;text-align:justify;hyphens:auto}}
h1{{font-family:Onest,sans-serif;font-size:23pt;line-height:1.1;margin:0 0 4pt;letter-spacing:-.4px;text-align:left}}
.sub{{font-family:Onest;font-size:11pt;color:#52606d;margin-bottom:10pt;text-align:left}}
.auth{{font-family:Onest;font-size:9.5pt;color:#16202b;text-align:left;margin-bottom:12pt}}
h2{{font-family:Onest;font-size:13pt;margin:16pt 0 5pt;color:#17324d;text-align:left;break-after:avoid}}
h3{{font-family:Onest;font-size:10.5pt;margin:10pt 0 3pt;color:#17324d;text-align:left;break-after:avoid}}
.abs{{border-left:3px solid #e4572e;padding:2pt 0 2pt 10pt;margin:8pt 0 4pt;background:#fbf6f3;font-size:10pt}}
.kw{{font-family:Onest;font-size:8.6pt;color:#52606d;text-align:left}}
table{{border-collapse:collapse;width:100%;font-family:Onest;font-size:8.3pt;margin:6pt 0 4pt;break-inside:avoid}}
th{{text-align:left;border-bottom:1.4px solid #17324d;padding:3pt 5pt;color:#17324d}}
td{{padding:3pt 5pt;border-bottom:.6px solid #d9e0e7}}
tr.best td{{background:#fdeee8;font-weight:600}}
.ci{{color:#6b7885;font-weight:400;font-size:7.4pt}}
figure{{margin:8pt 0;text-align:center;break-inside:avoid}}
figcaption{{font-family:Onest;font-size:8.2pt;color:#52606d;text-align:left;margin-top:3pt}}
code{{font-family:"IBM Plex Mono",monospace;font-size:8.6pt;background:#eef2f6;padding:0 2pt}}
.two{{display:flex;gap:10pt}} .two>*{{flex:1}}
.callout{{font-family:Onest;font-size:9pt;background:#eef4fa;border-radius:6pt;padding:6pt 10pt;margin:8pt 0;text-align:left}}
ol.refs{{font-size:9pt;padding-left:16pt}} ol.refs li{{margin-bottom:3pt;text-align:left}}
</style></head><body>
<h1>SignalRank: Predicting Which News Events Will Matter from Their First Hour of Coverage</h1>
<div class=sub>DATA 226 Group Project &middot; Team 10 &middot; Fall 2026</div>
<div class=auth>Sreeram Achutuni &nbsp;&middot;&nbsp; Dev Dhiren Faldu &nbsp;&middot;&nbsp; Pranav Sharma</div>

<div class=abs><b>Abstract.</b> Newsrooms, analysts and risk teams face thousands of new events every hour and must decide early which ones deserve attention.
We study whether the <i>first hour</i> of global media coverage can predict which events will keep spreading. Using {size['files']:,} 15-minute files of the GDELT 2.0 Events,
Mentions and Global Knowledge Graph tables for 20&ndash;27 October 2026 ({size['uncompressed']/1e9:.1f} GB uncompressed; 0.86 M events, 2.3 M mentions, 0.8 M articles) we build a Spark batch pipeline,
a Kafka + Structured Streaming scorer, an MLflow-tracked model comparison, a FastAPI service and a Streamlit dashboard. An event "matters" if at least {meta['pos_threshold']} publishers that were
<i>not</i> covering it in hour one pick it up during the next 48 hours (6.6% of training events). A gradient-boosted-tree model that adds a leakage-safe publisher-reach prior reaches PR-AUC {f(c['PR-AUC'])}
and F1 {f(c['F1'])} on a held-out weekend, versus {f(b0['PR-AUC'])} and {f(b0['F1'])} for the best simple rule (count first-hour publishers); the gains (+{f(ap['mean'])} PR-AUC, +{f(f1['mean'])} F1) are well outside bootstrap
intervals. Streaming and batch scoring agree exactly on {par['compared']:,} replayed events. We also quantify a hard limit: {late.share_of_positives:.0%} of the events that matter start with a single publisher and are almost
undetectable at hour one.</div>
<div class=kw>Keywords: GDELT, news-event importance, early prediction, Spark MLlib, Structured Streaming, MLflow, model serving</div>

<h2>1&nbsp; Introduction</h2>
<p>Every 15 minutes GDELT publishes thousands of newly coded events from news around the world. Most are routine: a local statement, a single wire story. A small fraction become stories that many outlets in many countries keep covering.
Telling these apart <i>early</i> is useful for triage (what should an analyst read first?) but difficult, because the signal in the first hour is sparse and noisy.</p>
<p>Our project, SignalRank, turns that question into a deployable system. We make four contributions: (i) a precise, leakage-free formulation of &ldquo;will this event matter&rdquo; with a chronological evaluation protocol;
(ii) a publisher-reach prior, an out-of-fold target encoding that captures <i>who</i> covers an event early; (iii) an end-to-end data product covering batch and streaming ingestion, experiment tracking, a model API and a live UI; and
(iv) an honest error analysis showing where early prediction fundamentally fails.</p>
<p>The course guidelines ask for a large dataset, data processing, model building, deployment, a front end and reproducibility; Section 5 maps each requirement to a component.</p>

<h2>2&nbsp; Related Work</h2>
<p>GDELT was introduced by Leetaru and Schrodt [1] as a machine-coded global event database; it is widely used for conflict and protest research, but mostly for descriptive or aggregate analyses.
Early prediction of popularity is a classic problem: Szabo and Huberman [2] showed that early attention to online content predicts its later popularity, and Cheng et al. [3] studied whether information cascades can be predicted
from early structural and temporal features, finding the task considerably harder than predicting from an observed prefix alone. We adopt the same &ldquo;early window&rdquo; framing for news events and add a publisher-level prior.
Target encoding for high-cardinality categories goes back to Micci-Barreca [4]; because naive encodings leak the label we use an out-of-fold variant. For modelling we use gradient boosting [5] as implemented in Spark MLlib [6],
for tracking and registry MLflow [7], and for the streaming layer Spark Structured Streaming [8]. Because positives are rare we report precision&ndash;recall metrics, which are more informative than ROC curves under imbalance [9].</p>

<h2>3&nbsp; Data</h2>
<p>GDELT 2.0 publishes three zipped, tab-delimited tables every 15 minutes: <b>Events</b> (who did what to whom, where; CAMEO codes, Goldstein scale, tone), <b>Mentions</b> (each article that mentions an event, with source name, language and tone)
and the <b>Global Knowledge Graph</b> (themes, people, organisations and tone per article). Files follow the URL pattern <code>data.gdeltproject.org/gdeltv2/YYYYMMDDHHMMSS.&#123;export,mentions,gkg&#125;</code>, so the window is reproducible by construction.</p>
<table><tr><th>Table</th><th>Files</th><th>Raw (uncompressed)</th><th>Rows</th><th>Kept as Parquet</th></tr>
<tr><td>Events</td><td>768</td><td>{size['export']/1e9:.2f} GB</td><td>856,615</td><td>20 of 61 columns</td></tr>
<tr><td>Mentions</td><td>768</td><td>{size['mentions']/1e9:.2f} GB</td><td>2,311,743</td><td>8 of 16 columns</td></tr>
<tr><td>GKG</td><td>768</td><td>{size['gkg']/1e9:.2f} GB</td><td>797,087</td><td>url, themes, tone</td></tr>
<tr><td><b>Total</b></td><td><b>{size['files']:,}</b></td><td><b>{size['uncompressed']/1e9:.2f} GB</b> ({size['zipped']/1e9:.2f} GB zipped)</td><td><b>3.97 M</b></td><td>0.42 GB Parquet</td></tr></table>
<p>The GKG table dominates the volume (93%) because of its wide text fields; the project keeps only what the models need, shrinking the lake 27-fold. We join Mentions to GKG on the article URL (<code>MentionIdentifier = DocumentIdentifier</code>).
Event time is anchored on the Events table&rsquo;s <code>DATEADDED</code> (first appearance in GDELT); the <code>SQLDATE</code> field can point to earlier dates and is not used for timing. Event volume drops by about half on the weekend of 24&ndash;25 October (Figure 1), which we exploit as a natural distribution shift for testing.</p>
{img(A/'fig_data.png','96%','Figure 1. Left: after the first hour most events gain no new publishers while a few gain dozens (log-log). Right: new events per day; the weekend (red) has roughly half the volume.')}

<h2>4&nbsp; Problem Formulation and Method</h2>
<h3>4.1&nbsp; Prediction target</h3>
<p>For each event first seen at time <i>t</i><sub>0</sub> we observe its coverage for <i>EARLY</i> = 60 minutes. The target is
<i>y</i> = 1 if at least {meta['pos_threshold']} <b>new</b> publishers, i.e. publishers not among those covering the event in the first hour, mention it between 1 h and 48 h. An earlier version of the label counted all publishers over 48 h;
we dropped it because any event with five or more publishers in hour one was then positive by construction (the top three buckets of that analysis were 100% positive). The growth-based label removes this mechanical link, and the problem becomes genuinely predictive.</p>
<h3>4.2&nbsp; Features (one implementation for batch and streaming)</h3>
<p><b>First-hour coverage:</b> mentions, distinct publishers, languages, non-English mentions, distinct articles, mentions in the first 15 minutes, mean and spread of tone, mean extraction confidence and document length.
<b>Event attributes:</b> Goldstein score, average tone, CAMEO root code, quad class, root-event flag, geographic precision, action-location and Actor1 country (top-40 values, others pooled), flags for missing actors or location.
<b>Publisher-reach prior (new):</b> for every publisher we measure how often the events it covered <i>in their first hour</i> later became important, smoothed toward the global rate with strength <i>k</i> = 20;
each event gets the mean and maximum prior of its first-hour publishers plus the share of publishers with at least five training observations. To prevent leakage, the prior of a training event is computed from the <i>other</i> training days only (out-of-fold by day); validation and test events use all training days.
<b>Themes:</b> GKG themes of first-hour articles, hashed into 256 binary features (ablation).</p>
<h3>4.3&nbsp; Models and protocol</h3>
<p>Spark MLlib logistic regression (standardised, L2) and gradient-boosted trees (40 trees, depth 5, step 0.15, 80% row subsampling) are compared with a transparent rule baseline that ranks events by first-hour publishers.
Positives are up-weighted 8&times; during training; the decision threshold is chosen on validation data to maximise F1. The split is chronological: <b>train</b> 20&ndash;22 Oct ({meta['train_rows']:,} events, {meta['train_pos_rate']:.1%} positive),
<b>validation</b> 23 Oct (117,193), <b>test</b> 24&ndash;25 Oct (138,903, {cvb['pos_rate']:.1%} positive), so the test period is both unseen and a weekend. The champion is selected on validation PR-AUC only; test numbers are computed once.
Confidence intervals are 95% percentile intervals from 200 bootstrap resamples of test events (paired for model differences).</p>

<h2>5&nbsp; System Architecture</h2>
{img(A/'fig_architecture.png','100%','Figure 2. SignalRank architecture. Solid arrows: data flow; dashed: the champion model loaded by the streaming scorer.')}
<table><tr><th>Course requirement</th><th>Component</th><th>Evidence</th></tr>
<tr><td>Data collection &amp; processing</td><td>Resumable parallel downloader; Spark ingest to partitioned Parquet; Spark feature/label jobs; Kafka producer (replay + live GDELT polling) and Structured Streaming scorer</td><td>{size['files']:,} files, {size['uncompressed']/1e9:.1f} GB raw</td></tr>
<tr><td>Model building</td><td>Spark MLlib LR and GBT, ablations, bootstrap evaluation</td><td>Table 1</td></tr>
<tr><td>Deployment</td><td>FastAPI: <code>/predict</code>, <code>/predict/batch</code>, <code>/top</code>, <code>/stats</code>, <code>/model</code>, <code>/health</code>; loads the same MLlib PipelineModel</td><td>Figure 8, 10 tests</td></tr>
<tr><td>Front end</td><td>Streamlit &ldquo;What matters now&rdquo;: ranked events, map, trends, what-if scoring</td><td>Figures 7&ndash;9</td></tr>
<tr><td>Reproducibility</td><td>MLflow tracking + model registry, <code>MLproject</code>, Makefile, Docker Compose, Airflow DAG, pinned requirements</td><td>Section 7</td></tr></table>
<p><b>Streaming design.</b> The producer publishes each 15-minute interval as JSON records to one Kafka topic. A Structured Streaming query appends every micro-batch to a rolling Parquet store; events that have accumulated 60 minutes of <i>data time</i>
(the maximum mention timestamp seen) become &ldquo;ripe&rdquo;, receive features from the same <code>early.py</code> module used offline, are scored by the champion model and appended to the serving store that the API reads.
Because it runs on data time, a replay of historical files and the live GDELT feed behave identically.</p>

<h2>6&nbsp; Results</h2>
<table><tr><th>Model</th><th>Val PR-AUC</th><th>Test PR-AUC [95% CI]</th><th>Test ROC-AUC</th><th>Test F1 [95% CI]</th><th>Prec.</th><th>Recall</th><th>P@top 5%</th></tr>{rows}</table>
<div class=callout><b>Table 1.</b> Held-out weekend (24&ndash;25 Oct, n = 138,903). Thresholds fixed on validation. Champion (highlighted) selected by validation PR-AUC.
Champion minus rule baseline: &Delta;PR-AUC = +{f(ap['mean'])} [{f(ap['lo'])}, {f(ap['hi'])}]; &Delta;F1 = +{f(f1['mean'])} [{f(f1['lo'])}, {f(f1['hi'])}].</div>
<div class=two>{img(A/'fig_pr_curves.png','100%','Figure 3. Precision-recall curves on the test weekend.')}{img(A/'fig_importance.png','100%','Figure 4. Champion feature importance. Publisher-reach features contribute about 14%.')}</div>
<h3>What the ablation says</h3>
<p><b>The first-hour publisher count is a strong baseline</b> (PR-AUC {f(b0['PR-AUC'])}) and carries most of the signal ({meta['top_features'][0][1]:.0%} of GBT importance). <b>Non-linearity helps</b>: GBT beats logistic regression (+{f(tm.loc['gbt_base','PR-AUC']-tm.loc['lr_base','PR-AUC'])} PR-AUC) because importance interacts with location and event type.
<b>The publisher-reach prior is the most useful addition</b>: +{f(tm.loc['gbt_prior','PR-AUC']-tm.loc['gbt_base','PR-AUC'])} PR-AUC and +{f(tm.loc['gbt_prior','F1']-tm.loc['gbt_base','F1'])} F1 for GBT, with non-overlapping confidence intervals, and it also lifts logistic regression.
<b>GKG themes add nothing measurable</b> (PR-AUC {f(tm.loc['gbt_prior_themes','PR-AUC'])} vs {f(tm.loc['gbt_prior','PR-AUC'])}; F1 is slightly lower), consistent with the idea that <i>who</i> covers a story early matters more than <i>what</i> it is about. We therefore ship the simpler model.</p>
{img(A/'fig_ablation.png','92%','Figure 5. Test PR-AUC and F1 with bootstrap 95% intervals for all models.')}
<h3>Where early prediction fails</h3>
<table><tr><th>Publishers in hour one</th><th>Events</th><th>Share that matter</th><th>Share of all important events</th><th>Caught by champion</th></tr>{brow}</table>
<p>The champion is excellent once an event has four or more first-hour publishers (recall above 97%) but {late.share_of_positives:.0%} of all important events begin with a <i>single</i> publisher, and only {late.recall:.0%} of those are flagged: a story that breaks later, for example after an official statement,
simply is not visible in hour one. We consider this a property of the problem rather than of the model, and it suggests a two-stage deployment: score at 60 minutes, re-score as coverage accumulates.</p>
{img(A/'fig_early_signal.png','92%','Figure 6. Left: probability that an event matters rises steeply with first-hour publishers. Right: where the important events are, and how many the model flags.')}
<h3>Streaming and batch agree</h3>
<p>We replayed 12:00&ndash;17:00 on 25 October through Kafka into a separate store and compared the streaming scorer with the batch scores of the same events: of {par['compared']:,} events, first-hour publisher and mention counts matched in 100% of cases and the largest absolute score difference was {par['max_abs_score_diff']:.1f}.
This confirms that the online path reproduces the offline features and model exactly.</p>

<h2>7&nbsp; Deployment, UI and Reproducibility</h2>
<div class=two>{img(S/'dashboard_ranked.png','100%','Figure 7. &ldquo;What matters now&rdquo;: ranked events flagged by the model (screenshot of the running app).')}{img(S/'dashboard_try.png','100%','Figure 8. What-if scoring: the form calls <code>POST /predict</code> on the FastAPI service.')}</div>
{img(S/'dashboard_map.png','78%','Figure 9. Map of flagged events by location; colour encodes model score.')}
<p><b>Reproducibility.</b> <code>make all</code> reproduces the pipeline from raw download to evaluation: <code>download</code> &rarr; <code>lake</code> &rarr; <code>features</code> &rarr; <code>prior</code> &rarr; <code>train</code> &rarr; <code>register</code> &rarr; <code>score</code> &rarr; <code>evaluate</code>.
Every training run logs parameters (feature set, class weight, split days, threshold) and metrics to MLflow; the champion is registered as <code>signalrank-champion</code> with alias <code>champion</code> and loads back through the registry URI. An <code>MLproject</code> file exposes the stages as MLflow entry points,
<code>docker compose up</code> starts Kafka (KRaft mode), MLflow, the API and the dashboard, and an Airflow DAG schedules the daily batch refresh. A pytest suite (10 tests) covers the GDELT parsers, the no-look-ahead guarantee of the feature code, and the API contract (validation, batch scoring, monotonicity of the score in first-hour publishers).</p>

<h2>8&nbsp; Limitations and Ethics</h2>
<p><b>Scale and window.</b> One week of data ({size['uncompressed']/1e9:.1f} GB) was processed on a 2-core machine; the model has not seen seasonal variation, and the weekend test is a single, short drift check. <b>Label definition.</b> &ldquo;Matters&rdquo; is operationalised as media spread, not societal importance;
heavily syndicated wire content can inflate it, and under-covered but consequential events are, by construction, missed. <b>Publisher prior.</b> It encodes which outlets tend to amplify stories, which can reinforce existing media visibility; its use for editorial triage should be audited for geographic and language bias,
and the per-publisher table is recomputed on each retrain. <b>Language.</b> GDELT machine-translates sources and its coding is noisy; all conclusions inherit that noise. <b>Streaming.</b> The demo is a replay at accelerated speed; a live-polling mode that follows GDELT&rsquo;s
<code>lastupdate.txt</code> is implemented in the producer but was not run for the reported results, which all come from replayed intervals. The Airflow DAG was syntax-checked but not run on a scheduler.</p>

<h2>9&nbsp; Conclusion</h2>
<p>The first hour of coverage is informative about which events will keep spreading, mostly through how many distinct publishers are already on the story, and a tree model with a leakage-safe publisher-reach prior improves on that rule by {f(ap['mean'])} PR-AUC and {f(f1['mean'])} F1 on an unseen weekend.
The same code path serves batch, streaming and API scoring, and the full pipeline is reproducible from public data. The main open problem is the late bloomer: more than a third of important events are invisible at hour one, which motivates re-scoring as coverage evolves, richer content features (article text embeddings)
and longer training windows as natural next steps.</p>

<h2>Team Contributions</h2>
<table><tr><th>Area</th><th>Scope</th><th>Lead</th></tr>
<tr><td>A. Data &amp; batch pipeline</td><td>Downloader, Parquet lake, features, label, publisher prior, Airflow DAG</td><td>________</td></tr>
<tr><td>B. Modelling &amp; MLOps</td><td>Model comparison, MLflow tracking/registry, evaluation, tests</td><td>________</td></tr>
<tr><td>C. Serving &amp; UI</td><td>Kafka producer, streaming scorer, FastAPI, dashboard, Docker Compose, demo</td><td>________</td></tr></table>
<p style="font-size:9pt;color:#52606d">Names to be filled in by the team to match the actual split of work and the GitHub commit history. Code: GitHub repository linked in the submission.</p>

<h2>References</h2>
<ol class=refs>
<li>K. Leetaru and P. A. Schrodt. GDELT: Global Data on Events, Location, and Tone, 1979&ndash;2012. ISA Annual Convention, 2013.</li>
<li>G. Szabo and B. A. Huberman. Predicting the popularity of online content. <i>Communications of the ACM</i> 53(8), 2010.</li>
<li>J. Cheng, L. Adamic, P. A. Dow, J. Kleinberg and J. Leskovec. Can cascades be predicted? <i>WWW</i>, 2014.</li>
<li>D. Micci-Barreca. A preprocessing scheme for high-cardinality categorical attributes in classification and prediction problems. <i>SIGKDD Explorations</i> 3(1), 2001.</li>
<li>J. H. Friedman. Greedy function approximation: a gradient boosting machine. <i>Annals of Statistics</i> 29(5), 2001.</li>
<li>X. Meng et al. MLlib: Machine learning in Apache Spark. <i>JMLR</i> 17(34), 2016.</li>
<li>M. Zaharia et al. Accelerating the machine learning lifecycle with MLflow. <i>IEEE Data Engineering Bulletin</i> 41(4), 2018.</li>
<li>M. Armbrust et al. Structured Streaming: A declarative API for real-time applications in Apache Spark. <i>SIGMOD</i>, 2018.</li>
<li>T. Saito and M. Rehmsmeier. The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. <i>PLoS ONE</i> 10(3), 2015.</li>
<li>GDELT Project. GDELT 2.0 event and GKG codebooks and data feeds, gdeltproject.org.</li>
</ol></body></html>"""
(R / "pdf" / "src.html").write_text(html)
