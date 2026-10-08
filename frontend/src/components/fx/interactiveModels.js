import { Group, Mesh, MeshStandardMaterial, MeshBasicMaterial, BoxGeometry, SphereGeometry,
  CylinderGeometry, TorusGeometry, IcosahedronGeometry, EdgesGeometry, LineSegments, LineBasicMaterial } from 'three'

// Original LINK objects, built from small shared geometries; no remote assets or post-processing.
export function buildInteractiveModel(kind) {
  const root = new Group(), parts = {}
  const ink = new MeshStandardMaterial({ color: '#30203f', metalness: .6, roughness: .3 })
  const violet = new MeshStandardMaterial({ color: '#be8bff', metalness: .45, roughness: .28, emissive: '#8746c3', emissiveIntensity: .22 })
  const orange = new MeshStandardMaterial({ color: '#ffac70', metalness: .4, roughness: .3, emissive: '#c2551b', emissiveIntensity: .18 })
  const paper = new MeshStandardMaterial({ color: '#dbceef', metalness: .12, roughness: .6 })
  const light = new MeshBasicMaterial({ color: '#dfb8ff' })
  const mesh = (geometry, material, parent = root, x = 0, y = 0, z = 0) => {
    const object = new Mesh(geometry, material); object.position.set(x, y, z); parent.add(object); return object
  }
  const box = (w, h, d, material, parent, x, y, z) => mesh(new BoxGeometry(w, h, d), material, parent, x, y, z)
  const line = (parent, length, x, y, z, material = light) => box(length, .025, .014, material, parent, x, y, z)
  if (kind === 'robot') {
    const head = new Group(); root.add(head); head.position.y = .36; parts.head = head
    const shell = mesh(new SphereGeometry(.67, 24, 16), violet, head); shell.scale.set(1.15, .86, .75)
    const face = mesh(new SphereGeometry(.58, 24, 16), ink, head, 0, -.01, .21); face.scale.set(1.1, .68, .55)
    parts.eyes = [-1, 1].map(side => {
      const eye = mesh(new SphereGeometry(.105, 12, 8), side < 0 ? light : orange, head, side * .25, .015, .52)
      eye.scale.set(.7, 1.15, .45); return eye
    })
    const smile = mesh(new TorusGeometry(.12, .018, 6, 16, Math.PI), light, head, 0, -.13, .535); smile.rotation.z = Math.PI
    box(.045, .24, .045, ink, head, 0, .56, 0); mesh(new SphereGeometry(.07, 12, 8), orange, head, 0, .7, 0)
    for (const side of [-1, 1]) { const ear = mesh(new CylinderGeometry(.13, .13, .13, 12), side < 0 ? violet : orange, head, side * .74, 0, 0); ear.rotation.z = Math.PI / 2 }
    const body = mesh(new SphereGeometry(.4, 20, 12), ink, root, 0, -.45, 0); body.scale.set(1.05, .85, .8)
    mesh(new TorusGeometry(.12, .025, 8, 24), orange, root, 0, -.44, .33)
    parts.arms = [-1, 1].map(side => {
      const arm = new Group(); arm.position.set(side * .42, -.36, 0); root.add(arm)
      const hand = mesh(new SphereGeometry(.13, 12, 8), side < 0 ? violet : orange, arm, side * .11, -.12, .01); hand.scale.y = 1.65
      return arm
    })
    const base = mesh(new TorusGeometry(.44, .025, 8, 48), violet, root, 0, -.83, 0); base.rotation.x = Math.PI / 2
  } else if (kind === 'book') {
    box(1.28, 1.6, .3, ink)
    box(1.17, 1.48, .31, paper, root, .035, 0, .015)
    box(.13, 1.63, .36, orange, root, -.63, 0, 0)
    const cover = new Group(); cover.position.set(-.63, 0, .2); root.add(cover); parts.cover = cover
    box(1.28, 1.63, .07, violet, cover, .64, 0, 0)
    const mark = mesh(new TorusGeometry(.22, .045, 8, 4), orange, cover, .65, .25, .05); mark.rotation.z = Math.PI / 4
    line(cover, .6, .64, -.26, .05); line(cover, .38, .64, -.38, .05)
    for (let i = 0; i < 5; i++) line(root, .82, .08, .4 - i * .19, .177, ink)
  } else if (kind === 'archive') {
    parts.cards = [0, 1, 2].map(i => {
      const card = new Group(); root.add(card)
      box(1.05, 1.35, .075, i === 1 ? orange : violet, card)
      box(.91, .83, .025, ink, card, 0, .12, .052)
      for (let row = 0; row < 3; row++) line(card, .52 - row * .08, -.05, .32 - row * .18, .074)
      line(card, .48, -.1, -.44, .055, ink)
      return card
    })
  } else {
    const core = mesh(new IcosahedronGeometry(kind === 'prism' ? .59 : .32, 0), violet); parts.core = core
    core.add(new LineSegments(new EdgesGeometry(core.geometry), new LineBasicMaterial({ color: '#f1d9ff', transparent: true, opacity: .65 })))
    parts.rings = [0, 1, 2].map(i => {
      const group = new Group(); group.rotation.set(.55 + i * .65, i * .65, i * .48); root.add(group)
      mesh(new TorusGeometry(.94, .017, 6, 64), i === 1 ? orange : violet, group)
      for (let j = 0; j < 2; j++) { const angle = i * 1.4 + j * Math.PI; mesh(new SphereGeometry(.065 + i * .018, 12, 8), i === 1 ? orange : light, group, Math.cos(angle) * .94, Math.sin(angle) * .94, 0) }
      return group
    })
  }
  return {
    root,
    pose({ expansion, pointerX, pointerY, reaction, reduced }) {
      if (parts.head) {
        parts.head.rotation.set(-pointerY * .13, pointerX * .22, reaction * .12)
        parts.eyes.forEach(eye => { eye.scale.y = 1.15 - expansion * .3 })
        parts.arms[0].rotation.z = -expansion * .5
        parts.arms[1].rotation.z = expansion * 1.4 + reaction * .5
        root.position.y = reduced ? 0 : reaction * .06
      }
      if (parts.cover) parts.cover.rotation.y = -expansion * 1.65
      parts.cards?.forEach((card, i) => {
        card.position.set((i - 1) * (.2 + expansion * .52), (i === 1 ? .12 : -.06) * expansion, (1 - i) * .2)
        card.rotation.z = (i - 1) * (.12 + expansion * .18)
      })
      parts.rings?.forEach((ring, i) => { ring.scale.setScalar(1 + expansion * (.12 + i * .16)); ring.rotation.y = i * .65 + expansion * .65 })
      if (parts.core) parts.core.rotation.y = expansion * Math.PI / 2
    },
  }
}
