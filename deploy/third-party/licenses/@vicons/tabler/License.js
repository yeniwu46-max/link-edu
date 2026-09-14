'use strict'
Object.defineProperty(exports, '__esModule', { value: true })
const vue_1 = require('vue')
const _hoisted_1 = {
  xmlns: 'http://www.w3.org/2000/svg',
  'xmlns:xlink': 'http://www.w3.org/1999/xlink',
  viewBox: '0 0 24 24'
}
exports.default = (0, vue_1.defineComponent)({
  name: 'License',
  render: function render(_ctx, _cache) {
    return (
      (0, vue_1.openBlock)(),
      (0, vue_1.createElementBlock)(
        'svg',
        _hoisted_1,
        _cache[0] ||
          (_cache[0] = [
            (0, vue_1.createElementVNode)(
              'g',
              {
                fill: 'none',
                stroke: 'currentColor',
                'stroke-width': '2',
                'stroke-linecap': 'round',
                'stroke-linejoin': 'round'
              },
              [
                (0, vue_1.createElementVNode)('path', {
                  d: 'M15 21H6a3 3 0 0 1-3-3v-1h10v2a2 2 0 0 0 4 0V5a2 2 0 1 1 2 2h-2m2-4H8a3 3 0 0 0-3 3v11'
                }),
                (0, vue_1.createElementVNode)('path', {
                  d: 'M9 7h4'
                }),
                (0, vue_1.createElementVNode)('path', {
                  d: 'M9 11h4'
                })
              ],
              -1 /* HOISTED */
            )
          ])
      )
    )
  }
})
