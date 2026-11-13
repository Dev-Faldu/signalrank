const fs=require('fs'),path=require('path');const {chromium}=require('playwright');
const F='node_modules/@fontsource/';
const face=(fam,w,st,file)=>`@font-face{font-family:"${fam}";font-weight:${w};font-style:${st};src:url(data:font/woff2;base64,${fs.readFileSync(F+file).toString('base64')}) format("woff2")}`;
const css=[['Source Serif 4',400,'normal','source-serif-4/files/source-serif-4-latin-400-normal.woff2'],['Source Serif 4',400,'italic','source-serif-4/files/source-serif-4-latin-400-italic.woff2'],['Source Serif 4',600,'normal','source-serif-4/files/source-serif-4-latin-600-normal.woff2'],['Source Serif 4',700,'normal','source-serif-4/files/source-serif-4-latin-700-normal.woff2'],
['Onest',400,'normal','onest/files/onest-latin-400-normal.woff2'],['Onest',600,'normal','onest/files/onest-latin-600-normal.woff2'],['Onest',700,'normal','onest/files/onest-latin-700-normal.woff2'],['IBM Plex Mono',400,'normal','ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2']].map(a=>face(...a)).join('\n');
fs.writeFileSync('report.html',fs.readFileSync('src.html','utf8').replace('<!--FONTS-->','<style>'+css+'</style>'));
(async()=>{const b=await chromium.launch();const p=await b.newPage();
await p.goto('file://'+path.resolve('report.html'));await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(600);
await p.pdf({path:'SignalRank_Final_Report.pdf',preferCSSPageSize:true,printBackground:true,displayHeaderFooter:true,headerTemplate:'<span></span>',footerTemplate:'<div style="width:100%;font-size:8px;font-family:sans-serif;color:#7b8794;text-align:center">SignalRank &middot; Team 10 &middot; <span class="pageNumber"></span></div>'});
await b.close()})();
