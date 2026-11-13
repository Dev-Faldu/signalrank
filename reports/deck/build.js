const pptxgen=require('pptxgenjs'),sharp=require('sharp'),fs=require('fs');
const A='../artifacts/',S='../screenshots/web/';
const INK='1B2140',MUT='5D6585',FAINT='8B93B1',AC='5B5BF0',AC2='8B5CF6',CY='22B8CF',OK='10B981',AMB='F59E0B';
const F='Calibri';
(async()=>{
await sharp(S+'try.png').extract({left:0,top:90,width:1360,height:590}).toFile('try_crop.png');
await sharp(S+'ranked.png').extract({left:0,top:0,width:1360,height:790}).toFile('ranked_crop.png');
await sharp(S+'map.png').extract({left:0,top:90,width:1360,height:720}).toFile('map_crop.png');
const pres=new pptxgen();pres.layout='LAYOUT_16x9';pres.title='SignalRank';pres.author='DATA 226 Team 10';
const W=10,H=5.625;
const bg=(s,k)=>s.background={path:`bg_${k}.png`};
const glass=(s,x,y,w,h,o={})=>s.addShape(pres.shapes.ROUNDED_RECTANGLE,{x,y,w,h,rectRadius:o.r||0.16,fill:{color:'FFFFFF',transparency:o.t==null?30:o.t},line:{color:'FFFFFF',width:1,transparency:15},shadow:{type:'outer',color:'5058A0',opacity:0.14,blur:14,offset:3,angle:90}});
const tx=(s,t,x,y,w,h,o={})=>s.addText(t,Object.assign({x,y,w,h,fontFace:F,color:INK,margin:0,valign:'top',isTextBox:true},o));
const title=(s,eyebrow,t)=>{tx(s,eyebrow.toUpperCase(),0.6,0.38,8,0.25,{fontSize:11,bold:true,color:AC,charSpacing:3});tx(s,t,0.6,0.64,8.8,0.8,{fontSize:26,bold:true,fontFace:'Cambria'});};
const foot=(s,n)=>{tx(s,'SignalRank · DATA 226 · Team 10',0.6,5.28,5,0.2,{fontSize:9,color:FAINT});tx(s,String(n),9.0,5.28,0.4,0.2,{fontSize:9,color:FAINT,align:'right'});};
const stat=(s,x,y,w,big,lab,col)=>{glass(s,x,y,w,1.15);tx(s,big,x+0.2,y+0.14,w-0.4,0.6,{fontSize:30,bold:true,color:col||AC});tx(s,lab,x+0.2,y+0.74,w-0.4,0.35,{fontSize:11,color:MUT});};
const pill=(s,t,x,y,w)=>{s.addShape(pres.shapes.ROUNDED_RECTANGLE,{x,y,w,h:0.3,rectRadius:0.15,fill:{color:'FFFFFF',transparency:25},line:{color:AC,width:0.75,transparency:55}});tx(s,t,x,y,w,0.3,{fontSize:10.5,bold:true,color:AC,align:'center',valign:'middle'});};
const num=(s,n,x,y,c)=>{s.addShape(pres.shapes.OVAL,{x,y,w:0.38,h:0.38,fill:{color:c||AC},line:{color:'FFFFFF',width:1.5}});tx(s,String(n),x,y,0.38,0.38,{fontSize:13,bold:true,color:'FFFFFF',align:'center',valign:'middle'});};

// 1 Title
let s=pres.addSlide();bg(s,'a');
glass(s,0.6,0.9,8.8,3.7,{r:0.3,t:38});
pill(s,'DATA 226  ·  Final project  ·  Team 10',0.95,1.25,3.3);
tx(s,'SignalRank',0.95,1.75,8,1.0,{fontSize:58,bold:true,fontFace:'Cambria',color:INK});
tx(s,'Which news will matter, one hour after it happens?',0.95,2.78,7.6,0.5,{fontSize:22,color:AC,bold:true});
tx(s,'Early-signal ranking of 11.5 GB of GDELT news events with Spark, Kafka, MLflow and a live scoring API',0.95,3.34,7.2,0.6,{fontSize:14,color:MUT});
tx(s,'Dev Dhiren Faldu  ·  Sreeram Achutuni  ·  Pranav Sharma',0.95,4.1,7.5,0.3,{fontSize:13,bold:true});
tx(s,'Instructor: Prof. Keeyong Han',0.95,4.38,7,0.25,{fontSize:11,color:MUT});
s.addNotes('Open with the question: a newsroom sees thousands of events per hour. Which ones will still be spreading tomorrow? Introduce the team. Each person presents the area they built. About 20 seconds.');

// 2 Question
s=pres.addSlide();bg(s,'b');title(s,'The question','We predict spread from the first 60 minutes only');
glass(s,0.6,1.65,2.7,2.35);num(s,1,0.8,1.85);tx(s,'Hour 0 to 1',0.8,2.35,2.3,0.3,{fontSize:15,bold:true});tx(s,'What the system sees: publishers, mentions, languages, tone, place, event type, publisher reach',0.8,2.72,2.3,1.2,{fontSize:11.5,color:MUT});
glass(s,3.65,1.65,2.7,2.35);num(s,2,3.85,1.85,AC2);tx(s,'Hours 1 to 48',3.85,2.35,2.3,0.3,{fontSize:15,bold:true});tx(s,'What happens next: do new publishers, who had not covered it in the first hour, pick the story up?',3.85,2.72,2.3,1.2,{fontSize:11.5,color:MUT});
glass(s,6.7,1.65,2.7,2.35);num(s,3,6.9,1.85,OK);tx(s,'The label',6.9,2.35,2.3,0.3,{fontSize:15,bold:true});tx(s,'"Matters" = at least 3 new publishers in hours 1 to 48. A growth label, so counting first-hour publishers cannot give the answer away',6.9,2.72,2.3,1.2,{fontSize:11.5,color:MUT});
stat(s,0.6,4.15,2.7,'5.7%','of test events are positive');stat(s,3.65,4.15,2.7,'138,903','held-out weekend events',AC2);stat(s,6.7,4.15,2.7,'60 min','early window, no look-ahead',OK);
foot(s,2);
s.addNotes('A first version defined importance as 5+ publishers over 48 hours, which is true by construction for events with 5 publishers in hour one. We caught that leakage and redefined the label as growth: new publishers after the first hour. Everything is evaluated on a chronological split, with the test set a weekend.');

// 3 Data
s=pres.addSlide();bg(s,'c');title(s,'Data','11.5 GB of real GDELT 2.0, one week of 15-minute files');
stat(s,0.6,1.65,2.7,'11.49 GB','uncompressed, 3.56 GB zipped');stat(s,3.65,1.65,2.7,'2,304','GDELT files, 20 to 26 Oct 2026',AC2);stat(s,6.7,1.65,2.7,'3.97 M','events after de-duplication',OK);
const rows=[['Events','0.35 GB','What happened: actors, CAMEO type, place, tone'],['Mentions','0.50 GB','Who covered it, when, in which language'],['GKG','10.64 GB','Themes and tone of the articles']];
rows.forEach((r,i)=>{const y=3.05+i*0.62;glass(s,0.6,y,8.8,0.52);tx(s,r[0],0.85,y,1.5,0.52,{fontSize:14,bold:true,valign:'middle'});tx(s,r[1],2.4,y,1.2,0.52,{fontSize:14,bold:true,color:AC,valign:'middle'});tx(s,r[2],3.7,y,5.5,0.52,{fontSize:12.5,color:MUT,valign:'middle'});});
foot(s,3);
s.addNotes('Course requirement is about 10 GB: we processed 11.49 GB uncompressed across 2,304 files. A resumable parallel downloader fetches the zips, Spark converts them to partitioned Parquet (0.42 GB), and everything downstream reads Parquet.');

// 4 Architecture
s=pres.addSlide();bg(s,'a');title(s,'Architecture','One feature code path for batch and streaming');
glass(s,0.6,1.55,8.8,3.55,{t:15});
s.addImage({path:A+'fig_architecture.png',x:0.6+(8.8-6.7)/2,y:1.65,w:6.7,h:6.7*767/1549});
foot(s,4);
s.addNotes('Walk the diagram left to right: GDELT files to Parquet lake, features and labels in Spark batch, training with MLlib and MLflow, champion registered with an alias. On the serving side the producer feeds Kafka, Structured Streaming scores ripe events with the same early.py features, and FastAPI plus the dashboard read the scored store. Dashed arrows are the champion model being loaded.');

// 5 Features
s=pres.addSlide();bg(s,'b');title(s,'Features','27 first-hour features, led by publisher count');
glass(s,0.6,1.55,5.6,3.55);
const imp=[['src_1h',26.9],['geo_country',16.2],['actor1_country',9.8],['pub_prior_max',8.4],['m_1h (mentions)',6.5],['pub_prior_mean',5.1],['cameo_root',3.8],['doclen_mean_1h',3.6]];
s.addChart(pres.charts.BAR,[{name:'Importance %',labels:imp.map(a=>a[0]).reverse(),values:imp.map(a=>a[1]).reverse()}],{x:0.7,y:1.65,w:5.4,h:3.35,barDir:'bar',chartColors:[AC],showTitle:true,title:'GBT feature importance (%)',titleFontSize:12,titleColor:INK,showValue:true,dataLabelFontSize:10,dataLabelColor:INK,dataLabelPosition:'outEnd',catAxisLabelColor:MUT,catAxisLabelFontSize:10,valAxisHidden:true,valGridLine:{style:'none'},catGridLine:{style:'none'},showLegend:false,barGapWidthPct:45});
glass(s,6.45,1.55,2.95,3.55);
tx(s,'What goes in',6.65,1.72,2.6,0.3,{fontSize:14,bold:true});
tx(s,[{text:'Reach and spread: publishers, mentions, languages',options:{bullet:true,breakLine:true}},{text:'Event: CAMEO type, Goldstein, tone, place',options:{bullet:true,breakLine:true}},{text:'Publisher reach prior: out-of-fold target encoding by day, so no label leakage',options:{bullet:true,breakLine:true}},{text:'Same early.py code in batch and streaming',options:{bullet:true}}],6.65,2.1,2.6,2.9,{fontSize:11.5,color:MUT,paraSpaceAfter:7});
foot(s,5);
s.addNotes('Top signal is first-hour publisher count, then where the event is and who the actor is. The publisher reach prior says how often these publishers historically get followed by new ones; it is computed out-of-fold by day so a day never sees its own labels. Batch and streaming import the very same feature function, which is why scores match exactly.');

// 6 Models
s=pres.addSlide();bg(s,'c');title(s,'Results','The model beats counting publishers');
glass(s,0.6,1.55,5.9,3.55);
const mods=[['Count publishers',0.474],['LogReg (base)',0.506],['LogReg (+prior)',0.537],['GBT (base)',0.553],['GBT (+prior)',0.585],['GBT (+prior+themes)',0.586]];
s.addChart(pres.charts.BAR,[{name:'PR-AUC',labels:mods.map(m=>m[0]),values:mods.map(m=>m[1])}],{x:0.7,y:1.65,w:5.7,h:3.35,barDir:'col',chartColors:['CBD5E1',  '9AA7F6','9AA7F6','8B7CF6',AC,'8B7CF6'],showTitle:true,title:'Test PR-AUC (higher is better)',titleFontSize:12,titleColor:INK,showValue:true,dataLabelFontSize:10,dataLabelColor:INK,dataLabelPosition:'outEnd',dataLabelFormatCode:'0.000',catAxisLabelColor:MUT,catAxisLabelFontSize:9,valAxisLabelColor:FAINT,valAxisLabelFontSize:9,valAxisMinVal:0.4,valAxisMaxVal:0.65,valGridLine:{color:'DDE1F0',size:0.5},catGridLine:{style:'none'},showLegend:false,barGapWidthPct:40});
stat(s,6.75,1.55,2.65,'+0.111','PR-AUC over baseline, 95% CI 0.106 to 0.116');
stat(s,6.75,2.85,2.65,'0.569','F1 for the champion vs 0.512 for the rule',AC2);
stat(s,6.75,4.15,2.65,'0.890','ROC-AUC, GBT with publisher prior',OK);
foot(s,6);
s.addNotes('Champion is GBT with the publisher prior, picked on validation PR-AUC. Adding the themes from GKG did not help on test, so we keep the simpler model. Intervals are bootstrap 95 percent. The simple rule of counting first-hour publishers is a strong baseline and we beat it with non-overlapping intervals.');

// 7 Weak spot
s=pres.addSlide();bg(s,'a');title(s,'Failure analysis','Our blind spot: stories that start with one publisher');
glass(s,0.6,1.55,5.9,3.55);
const bk=[['1',38.6,4.0],['2',19.4,59.8],['3',9.5,80.7],['4-5',13.4,98.2],['6-10',11.1,97.8],['>10',8.1,98.7]];
s.addChart(pres.charts.BAR,[{name:'Share of all important events (%)',labels:bk.map(b=>b[0]+' pub.'),values:bk.map(b=>b[1])},{name:'Recall (%)',labels:bk.map(b=>b[0]+' pub.'),values:bk.map(b=>b[2])}],{x:0.7,y:1.65,w:5.7,h:3.35,barDir:'col',barGrouping:'clustered',chartColors:[AMB,AC],showTitle:true,title:'By publishers at hour one',titleFontSize:12,titleColor:INK,showLegend:true,legendPos:'b',legendFontSize:10,legendColor:MUT,showValue:true,dataLabelFontSize:8.5,dataLabelColor:INK,dataLabelPosition:'outEnd',dataLabelFormatCode:'0',catAxisLabelColor:MUT,catAxisLabelFontSize:9.5,valAxisHidden:true,valGridLine:{style:'none'},catGridLine:{style:'none'},barGapWidthPct:40});
stat(s,6.75,1.55,2.65,'39%','of important events have only one publisher at hour one',AMB);
stat(s,6.75,2.85,2.65,'4%','recall on those late bloomers',AC);
tx(s,'With two or more publishers the model catches 60% to 99%. Next step: article text and a second look at 2 h and 6 h.',6.75,4.15,2.65,1.0,{fontSize:11.5,color:MUT});
foot(s,7);
s.addNotes('Be upfront about this. The largest group of eventually important events looks like nothing at hour one: a single publisher. We catch only 4 percent of those, and no first-hour feature set will fix that. That is why next steps are rescoring at 2 and 6 hours and adding article text.');

// 8 Streaming
s=pres.addSlide();bg(s,'b');title(s,'Streaming','Streaming reproduces batch scores exactly');
const st=[['Producer','Replays or polls each 15-minute GDELT interval into Kafka'],['Spark append','Micro-batches land in a rolling store'],['Ripe events','Events with 60 minutes of data time get early.py features and the champion'],['Serve','FastAPI and the dashboard read the scored store']];
st.forEach((a,i)=>{const x=0.6+i*2.25;glass(s,x,1.6,2.05,1.95);num(s,i+1,x+0.17,1.75,i%2?AC2:AC);tx(s,a[0],x+0.17,2.22,1.75,0.3,{fontSize:13.5,bold:true});tx(s,a[1],x+0.17,2.55,1.75,0.95,{fontSize:10.5,color:MUT});});
stat(s,0.6,3.8,2.7,'12,202','replayed events compared with batch');stat(s,3.65,3.8,2.7,'0.0','maximum score difference',OK);stat(s,6.7,3.8,2.7,'100%','identical first-hour counts',AC2);
foot(s,8);
s.addNotes('We replayed 12:00 to 17:00 of 25 Oct into a separate store and compared against batch scores for the same events: identical first-hour counts and zero score difference. Streaming works on data time, so replay and live GDELT behave the same. Live polling mode is implemented but we only ran replay.');

// 9 Demo
s=pres.addSlide();bg(s,'c');title(s,'Live demo','Ranked events, map, trends and what-if scoring');
glass(s,0.6,1.5,4.3,3.0,{t:20});s.addImage({path:'ranked_crop.png',x:0.68,y:1.58,w:4.14,h:4.14*790/1360,rounding:false});
glass(s,5.1,1.5,4.3,3.0,{t:20});s.addImage({path:'try_crop.png',x:5.18,y:1.58,w:4.14,h:4.14*590/1360});
tx(s,'Frosted-glass dashboard, a static site you can host on Vercel. The real Spark GBT, exported as 40 trees, scores in your browser and matches Spark to 1e-16.',0.6,4.62,8.8,0.55,{fontSize:12,color:MUT,align:'center'});
foot(s,9);
s.addNotes('DEMO SCRIPT, about 3 minutes. 1) Ranked tab: point at the KPIs, open one story. 2) Map tab: flagged events by place; zoom into Europe. 3) Trends tab: flagged per hour and by country. 4) Try an event: start with the Local protest preset (2 publishers, below threshold), switch to Wire-covered summit and show the score jump, then drag publishers from 1 upward. 5) Open localhost:8000/docs for /predict and /top if the full stack is running. The static site uses a snapshot of real scored events; the full Spark, Kafka and FastAPI stack runs from docker compose.');

// 10 Wrap
s=pres.addSlide();bg(s,'a');title(s,'Wrap-up','Reproducible, honest about limits, and ready to grow');
const cols=[['Reproducible',AC,['make all: raw files to registered model','MLflow: 7 runs, champion alias','Docker Compose: Kafka, API, dashboard, scorer','10 tests, CI workflow, issues and PR template']],['Limits',AMB,['One week of data, weekend test','"Matters" means media spread, not importance','Publisher prior may favour already-visible outlets','Replay run; live mode not run; Airflow DAG syntax-checked']],['Next',OK,['Rescore at 2 h and 6 h','Article text embeddings for late bloomers','Months of data, rolling retrain','Drift monitoring on the registered model']]];
cols.forEach((c,i)=>{const x=0.6+i*3.0;glass(s,x,1.55,2.8,2.7);s.addShape(pres.shapes.OVAL,{x:x+0.2,y:1.75,w:0.16,h:0.16,fill:{color:c[1]},line:{color:'FFFFFF',width:0.5}});tx(s,c[0],x+0.45,1.68,2.2,0.3,{fontSize:15,bold:true});
 tx(s,c[2].map((t,j)=>({text:t,options:{bullet:true,breakLine:j<3}})),x+0.2,2.12,2.45,2.1,{fontSize:10.5,color:MUT,paraSpaceAfter:5});});
glass(s,0.6,4.4,8.8,0.62,{t:25});tx(s,'Team 10  ·  Data and batch  ·  Modelling and MLOps  ·  Serving and UI   —   Dev Dhiren Faldu, Sreeram Achutuni, Pranav Sharma   —   Thank you, questions?',0.8,4.4,8.4,0.62,{fontSize:11.5,bold:true,align:'center',valign:'middle'});
foot(s,10);
s.addNotes('Each person presents their area. Contribution split should match the GitHub commit history; the guidelines ask for similar-sized contributions. Close the loop on the failure analysis: the biggest opportunity is the 39 percent of important events invisible at hour one.');

await pres.writeFile({fileName:'SignalRank_Presentation.pptx'});console.log('ok');
})();
