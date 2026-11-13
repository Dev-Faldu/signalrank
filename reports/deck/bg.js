const sharp=require('sharp');
const blobs={
 a:[['#c7d2fe',300,160,520],['#fbcfe8',1650,260,480],['#bae6fd',900,1000,560],['#bbf7d0',1750,950,300]],
 b:[['#e0e7ff',200,900,520],['#fde7f3',1500,120,520],['#cffafe',1000,420,420],['#ede9fe',1800,900,420]],
 c:[['#fbcfe8',1700,140,460],['#c7d2fe',260,260,520],['#bbf7d0',560,1060,420],['#bae6fd',1500,900,560]],
};
(async()=>{for(const k in blobs){
 const c=blobs[k].map(([f,x,y,r])=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${f}" opacity=".85"/>`).join('');
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><defs><filter id="b" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="110"/></filter><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f9faff"/><stop offset="1" stop-color="#eef2fb"/></linearGradient></defs><rect width="1920" height="1080" fill="url(#g)"/><g filter="url(#b)">${c}</g></svg>`;
 await sharp(Buffer.from(svg)).png().toFile(`bg_${k}.png`);}
 for (const f of ['../artifacts/fig_architecture.png','../screenshots/web/ranked.png','../screenshots/web/try.png','../screenshots/web/map.png']){const m=await sharp(f).metadata();console.log(f,m.width,m.height)}
})();
