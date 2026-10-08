import test from 'node:test'
import assert from 'node:assert/strict'
import { Scene, BoxGeometry, MeshStandardMaterial, Texture, SkinnedMesh, Bone, Skeleton } from 'three'
import { disposeScene } from '../src/components/fx/heroAvatarScene.js'

test('avatar cleanup disposes shared geometry, material, texture and skeleton exactly once', () => {
  const scene = new Scene()
  const geometry = new BoxGeometry()
  const texture = new Texture()
  const material = new MeshStandardMaterial({ map: texture })
  const skeleton = new Skeleton([new Bone()])
  const counts = { geometry: 0, material: 0, texture: 0, skeleton: 0 }
  geometry.addEventListener('dispose', () => counts.geometry++)
  material.addEventListener('dispose', () => counts.material++)
  texture.addEventListener('dispose', () => counts.texture++)
  const originalDispose = skeleton.dispose.bind(skeleton)
  skeleton.dispose = () => { counts.skeleton++; originalDispose() }
  const solid = new SkinnedMesh(geometry, material)
  solid.skeleton = skeleton
  scene.add(solid, solid.clone(false))
  disposeScene(scene)
  assert.deepEqual(counts, { geometry: 1, material: 1, texture: 1, skeleton: 1 })
  assert.equal(scene.children.length, 0)
  disposeScene(scene)
  assert.deepEqual(counts, { geometry: 1, material: 1, texture: 1, skeleton: 1 })
})
