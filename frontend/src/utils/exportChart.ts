export function downloadCSV(filename: string, headers: string[], rows: (string | number | null | undefined)[][]) {
  const escape = (v: string | number | null | undefined) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const content = [headers.map(escape), ...rows.map((r) => r.map(escape))]
    .map((line) => line.join(','))
    .join('\n')

  const blob = new Blob([`\uFEFF${content}`], { type: 'text/csv;charset=utf-8' })
  triggerDownload(blob, filename, 'text/csv')
}

export function exportChartAsPNG(container: HTMLElement | null, filename: string) {
  if (!container) return
  const svg = container.querySelector('svg')
  if (!svg) return

  const clone = svg.cloneNode(true) as SVGSVGElement
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  const width = parseFloat(svg.getAttribute('width') || svg.getBoundingClientRect().width.toFixed(0) || '800')
  const height = parseFloat(svg.getAttribute('height') || svg.getBoundingClientRect().height.toFixed(0) || '400')
  clone.setAttribute('width', String(width))
  clone.setAttribute('height', String(height))

  const serialized = new XMLSerializer().serializeToString(clone)
  const svgBlob = new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(svgBlob)

  const img = new Image()
  img.onload = () => {
    const scale = 2
    const canvas = document.createElement('canvas')
    canvas.width = width * scale
    canvas.height = height * scale
    const ctx = canvas.getContext('2d')
    ctx!.fillStyle = '#ffffff'
    ctx!.fillRect(0, 0, canvas.width, canvas.height)
    ctx!.drawImage(img, 0, 0, canvas.width, canvas.height)
    URL.revokeObjectURL(url)
    canvas.toBlob((blob) => {
      if (blob) triggerDownload(blob, filename, 'image/png')
    }, 'image/png')
  }
  img.onerror = () => URL.revokeObjectURL(url)
  img.src = url
}

function triggerDownload(blob: Blob, filename: string, type: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1500)
}