const fs = require('fs');
const p = 'C:/Users/User/Documents/rs36/ui/mockup.html';
let t = fs.readFileSync(p, 'utf8');

const a = t.indexOf('<!-- 3 -->');
const b = t.indexOf('<!-- 4 -->');
let f3 = t.slice(a, b);

const add = {
  'Gunstar Heroes': 'gunstar',
  'Phantasy Star IV': 'phantasy',
  'Sonic 3 &amp; Knuckles': 'sonic',
  'Streets of Rage 2': 'streets',
};
let n = 0;
for (const [name, art] of Object.entries(add)) {
  const old = '<div class="nm"><span class="t">' + name + '</span>';
  if (f3.includes(old)) {
    f3 = f3.replace(old, '<div class="cov cov-sm a-' + art + '"></div>' + old);
    n++;
  }
}
fs.writeFileSync(p, t.slice(0, a) + f3 + t.slice(b), 'utf8');
console.log('inserted in frame 3:', n);
