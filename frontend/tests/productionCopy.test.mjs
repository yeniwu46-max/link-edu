import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
const read = file => readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')
test('public login does not prefill shared credentials or offer unavailable social login', async () => {
  const source = await read('views/LandingView.vue')
  assert.doesNotMatch(source, /ref\('demo'\)|ref\('link123'\)|socialComingSoon|v-model:checked="remember"/)
})
test('profile has no fabricated contact or hidden classroom defaults', async () => {
  const source = await read('views/ProfileView.vue')
  assert.doesNotMatch(source, /陈老师|link-support@normal.edu|师范学院（演示）|settings.cameraDefault|settings.showDemoBadge/)
  assert.match(source, /VITE_SUPPORT_EMAIL/)
})
test('shared console styling applies to classroom and AI review as well', async () => {
  const shell = await read('layouts/AppShell.vue')
  const styles = await read('styles.css')
  assert.match(shell, /'protected-shell': protectedShell/)
  assert.match(shell, /protectedShell = computed\(\(\) => false\)/)
  assert.doesNotMatch(shell, /\['\/classroom', '\/ai-review'\]/)
  assert.match(shell, /!immersive && !protectedShell/)
  assert.doesNotMatch(styles.split('/* Dashboard mosaic:')[1], /\.app-shell(?!:not\(\.protected-shell\)|-)/)
})
