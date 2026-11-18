// Replace letter placeholders with cover art (CSS-only, tiny), add covers to game rows.
const fs = require('fs');
const path = 'C:/Users/User/Documents/rs36/ui/mockup.html';
let t = fs.readFileSync(path, 'utf8');

const css = `
  .cov{background-size:cover;background-position:center;overflow:hidden;position:relative}
  .cov:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(255,255,255,.16),rgba(0,0,0,.22))}
  .cov-sm{width:24px;height:18px;flex:0 0 24px;border-radius:2px}
  .a-sonic{background:linear-gradient(135deg,#12327f 0 38%,#3f8bff 38% 62%,#0d1f4d 62% 100%)}
  .a-crash{background:radial-gradient(circle at 35% 30%,#ffd27a 0 38%,#e8801f 38% 100%)}
  .a-lumines{background:linear-gradient(90deg,#0e3b3b 0 33%,#35c6c0 33% 66%,#0b2a2a 66% 100%)}
  .a-sor{background:linear-gradient(90deg,#5a1230 0 30%,#e0457b 30% 55%,#2a0b1c 55% 100%)}
  .a-mario{background:linear-gradient(180deg,#5fc0f0 0 55%,#2f8f3f 55% 100%)}
  .a-castle{background:linear-gradient(160deg,#3a0f18 0 45%,#b8452f 45% 70%,#140609 70% 100%)}
  .a-fft{background:linear-gradient(135deg,#1c2a55 0 50%,#d8c48a 50% 100%)}
  .a-gunstar{background:linear-gradient(135deg,#0f5a6b 0 45%,#ffd23f 45% 70%,#0a2b33 70% 100%)}
  .a-phantasy{background:linear-gradient(180deg,#26417f 0 60%,#e0bc63 60% 100%)}
  .a-disgaea{background:linear-gradient(140deg,#3c1c5c 0 55%,#a364d8 55% 100%)}
  .a-slug{background:linear-gradient(135deg,#4b5320 0 45%,#e08a2e 45% 75%,#20240f 75% 100%)}
  .a-ikaruga{background:linear-gradient(135deg,#0b0b0b 0 45%,#e8e8e8 45% 65%,#b42121 65% 100%)}
  .a-aladdin{background:linear-gradient(135deg,#3a1f6b 0 50%,#f0c04a 50% 100%)}
  .a-comix{background:linear-gradient(45deg,#e6d21e 0 45%,#1a1a1a 45% 70%,#8a7a12 70% 100%)}
  .a-contra{background:linear-gradient(160deg,#1b3a12 0 50%,#c8372a 50% 78%,#0d1c08 78% 100%)}
  .a-ristar{background:linear-gradient(135deg,#f2d24b 0 50%,#2b7bd6 50% 100%)}
  .a-shining{background:linear-gradient(180deg,#2a3f6b 0 55%,#c9d4e6 55% 100%)}
  .a-streets{background:linear-gradient(90deg,#8a1f45 0 40%,#ff8fae 40% 60%,#3c0d1f 60% 100%)}
  .a-story{background:linear-gradient(135deg,#5a3410 0 50%,#d9a13a 50% 100%)}
  .a-nocover{background:#20281f}
`;
if (!t.includes('.a-sonic')) t = t.replace('  /* systems */', css + '\n  /* systems */');

const rowArt = { S3:'sonic', CB:'crash', LM:'lumines', S2:'sor', MK:'mario', CK:'castle', FF:'fft', GH:'gunstar', PS:'phantasy', DS:'disgaea', MY:'slug', IG:'ikaruga' };
for (const [tag, art] of Object.entries(rowArt)) {
  const re = new RegExp('<div class="cov" style="background:#[0-9a-fA-F]{6}">' + tag + '</div>');
  t = t.replace(re, '<div class="cov a-' + art + '"></div>');
}

const gameArt = {
  'Aladdin':'aladdin', 'Castlevania: Bloodlines':'castle', 'Comix Zone':'comix', 'Contra: Hard Corps':'contra',
  'Gunstar Heroes':'gunstar', 'Phantasy Star IV':'phantasy', 'Ristar':'ristar', 'Shining Force II':'shining',
  'Sonic 3 &amp; Knuckles':'sonic', 'Sonic the Hedgehog 2':'sonic', 'Streets of Rage 2':'streets', 'The Story of Thor':'story'
};
for (const [name, art] of Object.entries(gameArt)) {
  const old = '<div class="nm"><span class="t">' + name + '</span>';
  if (t.includes(old) && !t.includes('a-' + art + '"></div>' + old)) {
    t = t.replace(old, '<div class="cov cov-sm a-' + art + '"></div>' + old);
  }
}
// keep one row without art to demonstrate the fallback
t = t.replace('<div class="cov cov-sm a-ristar"></div><div class="nm"><span class="t">Ristar</span>',
              '<div class="cov cov-sm a-nocover"></div><div class="nm"><span class="t">Ristar</span>');

fs.writeFileSync(path, t, 'utf8');
console.log('covers applied; art classes:', (t.match(/a-[a-z]+/g) || []).length);
