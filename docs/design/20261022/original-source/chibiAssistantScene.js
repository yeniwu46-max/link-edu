import { Group, Mesh, SphereGeometry, CapsuleGeometry, CylinderGeometry, MeshStandardMaterial, MeshBasicMaterial, CatmullRomCurve3, TubeGeometry, Vector3 } from 'three';

// Original, locally constructed character: no external model or texture downloads.
export function createChibiAssistant() {
  const root = new Group(), head = new Group();
  root.name = 'LINK chibi assistant';
  head.position.y = 1.64;
  root.add(head);
  const material = (color, roughness = .55) => new MeshStandardMaterial({ color, roughness, metalness: 0 });
  const skin = material(0xffd8bc), blush = material(0xf3a6a7), hair = material(0x42304e), fringe = material(0x59405f);
  const violet = material(0xa39adf), cream = material(0xfff8eb), teal = material(0x88d8cf), ink = material(0x31263c, .3);
  const shine = new MeshBasicMaterial({ color: 0xffffff });
  const sphere = new SphereGeometry(1, 32, 24);
  function ball(parent, mat, position, scale) {
    const mesh = new Mesh(sphere, mat);
    mesh.position.set(...position); mesh.scale.set(...scale); parent.add(mesh); return mesh;
  }
  function curve(parent, mat, points, radius = .018) {
    const path = new CatmullRomCurve3(points.map(p => new Vector3(...p)));
    const mesh = new Mesh(new TubeGeometry(path, 24, radius, 8, false), mat);
    parent.add(mesh); return mesh;
  }
  ball(head, hair, [0, .08, -.13], [.62, .60, .48]);
  ball(head, skin, [0, -.015, .05], [.54, .51, .46]);
  for (const side of [-1, 1]) {
    ball(head, hair, [side * .47, -.20, -.07], [.20, .33, .28]);
    ball(head, skin, [side * .53, -.06, .035], [.085, .115, .08]);
  }
  for (const [x, y, z, angle, width] of [[-.31,.34,.32,-.55,.22],[-.05,.40,.35,-.5,.25],[.24,.37,.32,-.55,.24]]) {
    const lock = ball(head, fringe, [x,y,z], [width,.24,.13]); lock.rotation.z = angle;
  }
  const eyes = [];
  for (const side of [-1, 1]) {
    const eye = new Group(); eye.position.set(side * .205, .015, .473); head.add(eye); eyes.push(eye);
    ball(eye, ink, [0,0,0], [.069,.096,.025]);
    ball(eye, shine, [-.018,.035,.023], [.023,.027,.008]);
    ball(eye, shine, [.025,-.032,.024], [.009,.011,.005]);
    ball(head, blush, [side*.325,-.135,.405], [.095,.037,.024]);
    curve(head, hair, [[side*.13,.17,.45],[side*.205,.19,.445],[side*.275,.17,.42]], .013);
  }
  ball(head, skin, [0,-.10,.51], [.038,.030,.035]);
  const smile = curve(head, ink, [[-.075,-.20,.465],[0,-.23,.488],[.075,-.20,.465]], .015);
  const mouth = ball(head, ink, [0,-.215,.478], [.045,.035,.018]); mouth.visible = false;
  curve(head, violet, [[-.63,.02,-.02],[-.58,.45,-.04],[0,.67,-.06],[.58,.45,-.04],[.63,.02,-.02]], .045);
  for (const side of [-1, 1]) {
    ball(head, cream, [side*.615,.005,0], [.105,.16,.145]);
    ball(head, violet, [side*.67,.005,.035], [.066,.118,.10]);
  }
  curve(head, violet, [[-.64,-.04,.10],[-.57,-.26,.31],[-.28,-.29,.50]], .022);
  ball(head, teal, [-.25,-.285,.51], [.065,.035,.035]);
  const skirt = new Mesh(new CylinderGeometry(.21,.30,.25,32), violet);
  skirt.position.set(0,.49,0); skirt.scale.z=.75; root.add(skirt);
  const hem = new Mesh(new CylinderGeometry(.30,.30,.04,32), cream);
  hem.position.set(0,.365,0); hem.scale.z=.75; root.add(hem);
  const torso = new Mesh(new CapsuleGeometry(.235,.27,8,24), violet);
  torso.position.set(0,.85,0); torso.scale.set(1.12,1,.85); root.add(torso);
  ball(root, cream, [0,1.08,.11], [.20,.065,.15]);
  curve(root, cream, [[-.075,1.06,.205],[-.075,.94,.224]], .013);
  curve(root, cream, [[.075,1.06,.205],[.075,.94,.224]], .013);
  ball(root, teal, [0,.79,.207], [.075,.062,.020]);
  curve(root, cream, [[-.025,.79,.23],[-.005,.77,.234],[.035,.81,.23]], .009);
  const arms = [];
  for (const side of [-1, 1]) {
    const arm = new Group(); arm.position.set(side*.28,1.015,0); root.add(arm); arms.push(arm);
    const sleeve = new Mesh(new CapsuleGeometry(.09,.18,6,16), violet); sleeve.position.y=-.12; arm.add(sleeve);
    ball(arm, skin, [0,-.29,.015], [.085,.09,.08]);
    arm.rotation.z = side*.24;
    ball(root, skin, [side*.14,.285,.02], [.09,.15,.085]);
    ball(root, cream, [side*.14,.15,.08], [.125,.085,.19]);
    ball(root, violet, [side*.14,.16,.215], [.095,.025,.045]);
  }
  function pose(time, state = 'idle', level = 0, pointer = 0, reduced = false) {
    root.position.y = reduced ? 0 : Math.sin(time*1.7)*.012;
    head.rotation.set(state === 'listening' ? -.045 : 0, reduced ? 0 : pointer*.17, state === 'thinking' ? .10 : 0);
    const blinking = !reduced && time%4.8 > 4.63;
    for (const eye of eyes) eye.scale.y = blinking ? .12 : 1;
    arms[1].rotation.z = state === 'listening' ? .70 + (reduced ? 0 : Math.sin(time*3)*.05) : .24;
    const speaking = state === 'speaking' && level > .04;
    smile.visible = !speaking; mouth.visible = speaking;
    mouth.scale.y = .025 + Math.min(1,Math.max(0,level))*.055;
  }
  pose(0);
  return { root, pose };
}
