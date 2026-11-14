// Generate the coordinated light and dark library plans used by Locate.
const fs = require('fs');
const path = require('path');
const geometry = require('./src/floorGeometry.json');
const out = path.join(__dirname, 'public', 'maps');
fs.mkdirSync(out, { recursive: true });
const plans = {
  1: { upper: 'ZONE A · WINDOWS', lower: 'ZONE B · ENTRANCE', upperCount: 3, lowerCount: 2 },
  2: { upper: 'ZONE A · STUDY TABLES', lower: 'ZONE B · SOUTH READING', upperCount: 3, lowerCount: 3 },
  3: { upper: 'EAST · READING TABLES', lower: 'WEST · BOOKSHELVES', upperCount: 2, lowerCount: 3 },
};
for (const [floor, plan] of Object.entries(plans)) for (const dark of [false, true]) {
  const c = dark
    ? { bg:'#0e2230', wall:'#8aa8bc', room:'#203d50', table:'#315d76', text:'#eef5fa', mute:'#aec6d6', hall:'#182f3f', shelf:'#55778c', seat:'#b7d5e5' }
    : { bg:'#f8f7f2', wall:'#506b7d', room:'#e6edf0', table:'#c2dbe9', text:'#1d3747', mute:'#425f70', hall:'#eef3f2', shelf:'#a5bdc8', seat:'#527e98' };
  const room = (x,y,w,h,label,sub='') => `<g><rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${c.room}" stroke="${c.wall}" stroke-width="3"/><text x="${x+w/2}" y="${y+h/2-3}" text-anchor="middle" class="room-label">${label}</text>${sub ? `<text x="${x+w/2}" y="${y+h/2+15}" text-anchor="middle" class="small">${sub}</text>` : ''}</g>`;
  const table = (x,y,n,shape = 'rect') => shape === 'round'
    ? `<g><circle cx="${x+50}" cy="${y+23}" r="23" fill="${c.table}" stroke="${c.wall}" stroke-width="2"/><text x="${x+50}" y="${y+27}" text-anchor="middle" font-size="10">Table ${n}</text>${[[43,-11],[67,-2],[78,18],[67,39],[43,48],[19,39],[8,18],[19,-2]].map(([dx,dy])=>`<circle cx="${x+dx+7}" cy="${y+dy+4}" r="5" fill="${c.seat}"/>`).join('')}</g>`
    : shape === 'arc'
    ? `<g><path d="M ${x+4} ${y+1} Q ${x+50} ${y+19} ${x+96} ${y+1} L ${x+96} ${y+9} Q ${x+50} ${y+27} ${x+4} ${y+9} Z M ${x+4} ${y+44} Q ${x+50} ${y+26} ${x+96} ${y+44} L ${x+96} ${y+52} Q ${x+50} ${y+34} ${x+4} ${y+52} Z" fill="${c.table}" stroke="${c.wall}" stroke-width="2"/><text x="${x+50}" y="${y+67}" text-anchor="middle" class="small">Table ${n}</text>${[[4,-10],[28,-3],[56,-3],[80,-10],[4,54],[28,47],[56,47],[80,54]].map(([dx,dy])=>`<rect x="${x+dx}" y="${y+dy}" width="16" height="7" rx="3" fill="${c.seat}"/>`).join('')}</g>`
    : `<g><rect x="${x}" y="${y}" width="100" height="45" rx="5" fill="${c.table}" stroke="${c.wall}" stroke-width="2"/><text x="${x+50}" y="${y+28}" text-anchor="middle" class="small">Table ${n}</text>${[0,1,2,3].map(i => `<rect x="${x+9+i*23}" y="${y-12}" width="16" height="9" rx="3" fill="${c.seat}"/><rect x="${x+9+i*23}" y="${y+48}" width="16" height="9" rx="3" fill="${c.seat}"/>`).join('')}</g>`;
  const shelf = (x,y) => `<g><rect x="${x}" y="${y}" width="115" height="16" rx="2" fill="${c.shelf}"/>${[1,2,3,4,5,6].map(i=>`<path d="M${x+i*16} ${y+3}v10" stroke="${c.bg}" stroke-width="2"/>`).join('')}</g>`;
  const positions = geometry[floor];
  const shapes = {
    '1': { upper: ['rect', 'round', 'arc'], lower: ['arc', 'rect'] },
    '2': { upper: ['arc', 'rect', 'round'], lower: ['round', 'arc', 'rect'] },
    '3': { upper: ['arc', 'round'], lower: ['rect', 'arc', 'round'] },
  };
  const upper = positions.upperX.map((x,i)=>table(x,positions.upperY,i+1, shapes[floor].upper[i])).join('');
  const lower = positions.lowerX.map((x,i)=>table(x,positions.lowerY,i+1, shapes[floor].lower[i])).join('');
  const shelves = floor === '1' ? [[40,225],[40,255],[40,285],[40,465],[40,495]] : floor === '2' ? [[35,225],[35,255],[35,285],[35,465],[35,495]] : [[40,235],[40,265],[180,570],[315,570],[450,570]];
  const upperToilet = floor === '2' ? 'FEMALE TOILET' : 'MALE TOILET';
  const lowerToilet = floor === '2' ? 'MALE TOILET' : 'FEMALE TOILET';
  const callRoom = floor === '1' ? room(30,55,155,130,'CALL ROOM') : floor === '2' ? room(30,555,150,105,'CALL ROOM') : room(510,55,155,130,'CALL ROOM');
  const upperRooms = room(190,55,115,130,'STAIRS') + room(310,55,150,130,upperToilet) + callRoom;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700" role="img" aria-labelledby="title desc">
<title id="title">Floor ${floor} library plan</title><desc id="desc">Library floor plan showing reading zones, tables, lift, stairs, call room, toilets, water coolers, shelves and research scholar hall.</desc>
<style>text{font-family:system-ui,sans-serif;fill:${c.text}}.heading{font-size:21px;font-weight:700}.zone{font-size:16px;font-weight:700}.room-label{font-size:14px;font-weight:600}.small{font-size:12px;fill:${c.text}}.muted{font-size:12px;fill:${c.mute}}</style>
<rect x="8" y="8" width="984" height="684" rx="12" fill="${c.bg}" stroke="${c.wall}" stroke-width="5"/>
<path d="M32 330H968V410H32z M725 160H785V635H725z" fill="${c.hall}"/><text x="420" y="348" class="muted">MAIN CORRIDOR</text>
<text x="30" y="37" class="heading">FLOOR ${floor}</text>
${upperRooms}
${room(795,165,165,75,'LIFT')}${room(795,248,165,135,'RESEARCH SCHOLAR','READING HALL')}${room(795,465,165,150,lowerToilet)}
<g><rect x="470" y="150" width="34" height="30" rx="4" fill="${c.table}" stroke="${c.wall}"/><text x="487" y="170" text-anchor="middle" class="small">W</text><text x="510" y="170" class="muted">Water</text><rect x="755" y="480" width="32" height="30" rx="4" fill="${c.table}" stroke="${c.wall}"/><text x="771" y="500" text-anchor="middle" class="small">W</text><text x="705" y="525" class="muted">Water</text></g>
<text x="220" y="225" class="zone">${plan.upper}</text><text x="220" y="455" class="zone">${plan.lower}</text>${upper}${lower}
${shelves.map(([x,y])=>shelf(x,y)).join('')}<text x="45" y="215" class="muted">BOOKSHELVES</text><text x="${floor === '3' ? 180 : 45}" y="${floor === '3' ? 565 : 440}" class="muted">BOOKSHELVES</text>
<g stroke="${c.seat}" stroke-width="5"><path d="M520 10h90 M630 10h90 M740 10h90 M850 10h90"/></g><text x="600" y="655" class="muted">${floor === '1' ? 'MAIN ENTRANCE' : 'FLOOR LANDING'}</text>
</svg>`;
  fs.writeFileSync(path.join(out, `floor-${floor}${dark ? '-dark' : ''}.svg`), svg);
}
