const fs = require('fs');
const p = 'C:/Users/User/Documents/rs36/ui/mockup.html';
let t = fs.readFileSync(p, 'utf8');

const a = t.indexOf('<!-- 1 -->');
const b = t.indexOf('<!-- 2 -->');
const head = t.slice(0, a), f1 = t.slice(a, b), tail = t.slice(b);
const cleaned = f1.replace(/<div class="cov cov-sm a-[a-z]+"><\/div>/g, '');
fs.writeFileSync(p, head + cleaned + tail, 'utf8');
console.log('removed duplicates in frame 1:', (f1.length - cleaned.length));
