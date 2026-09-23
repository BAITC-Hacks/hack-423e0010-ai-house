import type { Category, Profile } from '../domain/selection'

const palettes = {
  sage: ['#dce5d9', '#7d9683', '#234a3b', '#afc2a8'],
  clay: ['#efded1', '#c88c75', '#744b3b', '#e0b49a'],
  blue: ['#dce3e8', '#839cab', '#344d66', '#bccad7'],
  rose: ['#eadbdd', '#be8894', '#7a455c', '#d8b4b7'],
  sand: ['#ede6d3', '#b9a172', '#6b6248', '#d2c7a2'],
  forest: ['#d6e2da', '#729c85', '#264e3f', '#abc1ae'],
}
export function Artwork({
  palette,
  category,
  name,
  compact = false,
}: {
  palette: Profile['artwork']
  category: Category
  name: string
  compact?: boolean
}) {
  const [bg, mid, dark, light] = palettes[palette]
  const place = ['Банкетный зал', 'Загородная площадка', 'Отель', 'Ресторан'].includes(category)
  const floral = category === 'Флорист' || category === 'Декоратор'
  return (
    <div
      className={`artwork artwork-${palette} ${compact ? 'artwork-compact' : ''}`}
      style={{ backgroundColor: bg }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 360 220" fill="none" preserveAspectRatio="xMidYMid slice">
        <circle cx="310" cy="20" r="135" fill={light} opacity=".5" />
        <circle cx="38" cy="223" r="100" stroke={mid} strokeWidth="1" opacity=".55" />
        <circle cx="38" cy="223" r="117" stroke={mid} strokeWidth="1" opacity=".4" />
        {place ? (
          <>
            <path d="M97 220V94a83 83 0 0 1 166 0v126" fill={mid} />
            <path d="M122 220V98a58 58 0 0 1 116 0v122" fill={dark} />
            <path d="M180 40v180M120 116h119M120 173h119" stroke={light} strokeWidth="3" />
            <path d="m54 199 35-80 28 80M251 220l36-100 36 100" fill={dark} opacity=".8" />
            <path d="M49 218h274" stroke={light} strokeWidth="2" />
          </>
        ) : floral ? (
          <>
            <path
              d="M172 220q-15-63-70-116m70 116q27-63 81-94m-81 94L185 63"
              stroke={dark}
              strokeWidth="3"
            />
            {[
              { x: 103, y: 105, c: mid },
              { x: 185, y: 66, c: dark },
              { x: 251, y: 118, c: mid },
            ].map(({ x, y, c }) => (
              <g key={x} transform={`translate(${x} ${y})`}>
                {[0, 60, 120, 180, 240, 300].map((angle) => (
                  <ellipse
                    key={angle}
                    cx="0"
                    cy="-20"
                    rx="15"
                    ry="24"
                    fill={c}
                    transform={`rotate(${angle})`}
                  />
                ))}
                <circle r="13" fill={light} />
              </g>
            ))}
            <path d="M157 192q-62-4-51-40 50-2 51 40M187 183q56-50 60-7-24 25-60 7" fill={dark} />
          </>
        ) : (
          <>
            <path d="M93 229V104a87 87 0 0 1 174 0v125" fill={light} />
            <path d="M107 229V104a73 73 0 0 1 146 0v125" stroke={mid} strokeWidth="1" />
            <ellipse
              cx="180"
              cy="145"
              rx="95"
              ry="34"
              stroke={mid}
              opacity=".6"
              transform="rotate(-24 180 145)"
            />
            <text
              x="180"
              y="177"
              textAnchor="middle"
              fill={dark}
              fontSize="145"
              fontFamily="Georgia, serif"
              fontStyle="italic"
            >
              {name.charAt(0)}
            </text>
            <path
              d="M277 206c-15-27-6-53 4-64m-7 40c-25-5-30-24-23-34 20 2 29 17 23 34m4-12c-5-21 6-34 21-33 4 17-5 31-21 33"
              fill={dark}
              opacity=".65"
            />
            <circle cx="79" cy="111" r="13" fill={mid} opacity=".8" />
            <circle cx="79" cy="111" r="20" stroke={mid} opacity=".5" />
          </>
        )}
        <path
          d="m300 135 3 9 9 3-9 3-3 9-3-9-9-3 9-3zM61 54l2 7 7 2-7 2-2 7-2-7-7-2 7-2z"
          fill={dark}
          opacity=".65"
        />
      </svg>
      {!compact && (
        <>
          <span className="artwork-caption">TANDAU / ИЛЛЮСТРАЦИЯ</span>
          <span className="artwork-initial">{name.charAt(0)}</span>
        </>
      )}
    </div>
  )
}
