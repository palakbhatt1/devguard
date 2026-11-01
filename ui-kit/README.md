# DejaQ UI Kit & Design System

A modern, high-conversion **Cosmic Glass / Dark Stippled SaaS** design system extracted directly from DejaQ. This kit contains everything you need to drop this aesthetic into any new web application, landing page, or dashboard.

---

## 📁 What's Included in this Folder

```
ui-kit/
├── assets/                       # All background images, textures & icons
│   ├── hero_bg_full.jpg          # Primary high-res starry night sky background
│   ├── hero_bg_clean.jpg         # Clean high-res celestial background
│   ├── hero_bg_1920.jpg          # 1920x1080 optimized background
│   ├── hero_bg.jpg               # Standard hero background
│   ├── alt_bg.jpg                # Alternative deep blue background
│   ├── cloud_overlay.jpg         # Fog / ambient cloud texture
│   ├── cloud_overlay_clean.jpg   # Ambient cloud texture (cleaned)
│   ├── halftone_pattern.jpg      # Stipple dot-matrix texture
│   ├── halftone_pat.jpg          # Compact stipple tile
│   ├── tex_dots.jpg              # Micro dot pattern
│   ├── tex_grid.jpg              # Subtle coordinate grid
│   ├── sky_glow.jpg              # Blue radial atmosphere glow
│   ├── logo_star.png             # DejaQ 4-point sparkle star
│   ├── logo_icon.png             # DejaQ brand badge
│   ├── small_star_box.png        # Square icon badge with star
│   ├── small_icon.png            # Compact star icon
│   ├── subtopic_card.png         # Reference widget asset
│   ├── widgets_preview.png       # Reference component sheet
│   ├── design_sheet.jpg          # Master art direction sheet
│   └── landing_reference.jpg     # Visual landing reference
├── ui-style.css                  # Complete standalone CSS stylesheet & design tokens
├── demo-landing.html             # Standalone, interactive landing page demo
├── components.html               # Living component showcase & design token guide
└── README.md                     # This complete integration manual
```

---

## 🎨 Visual Identity & Key Aesthetics

1. **Canvas Base**: Ultra-deep space obsidian navy (`#050a14`).
2. **Photographic Sky Backdrop**: High-fidelity starry night sky photography (`hero_bg_full.jpg`).
3. **Halftone Stipple Overlay**: Mathematical radial dot matrix (`radial-gradient(circle, rgba(255,255,255,0.08) 1px, transparent 1px) 10px 10px`) set to `mix-blend-mode: overlay` to produce a tactile printed/retro-futuristic look.
4. **3D Perspective Glass Slab**: Downward perspective tilt (`perspective(1000px) rotateX(-6deg) rotateY(-12deg) rotateZ(-2.5deg)`) with heavy frosted glass (`backdrop-filter: blur(32px) saturate(190%)`), multi-layer cast shadows, and top specular glow reflection.
5. **Cream Vintage Accents**: Soft off-white / parchment cream (`#f0ece1`) buttons and callout banners paired with high-contrast obsidian elements.
6. **Dual Typography**:
   - **Primary / Body / Headings**: Google Fonts [`Plus Jakarta Sans`](https://fonts.google.com/specimen/Plus+Jakarta+Sans) (weights: 400, 500, 600, 700, 800)
   - **Technical / Monospace / Badges**: Google Fonts [`Space Grotesk`](https://fonts.google.com/specimen/Space+Grotesk) (weights: 500, 600, 700)

---

## 🚀 Quick Start (In Under 2 Minutes)

### Option A: Open Immediately in Browser
Double-click `demo-landing.html` or `components.html` to view the live interface immediately in your browser. All assets are referenced locally via relative paths (`./assets/...`).

### Option B: Copy into Another Project
1. Copy the entire `ui-kit/assets/` directory into your project's public folder (e.g. `public/assets/` or `assets/`).
2. Copy `ui-style.css` into your styles directory (or import it in your main CSS/HTML).
3. Add the Google Fonts snippet to your `<head>`:
   ```html
   <link rel="preconnect" href="https://fonts.googleapis.com">
   <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
   <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
   ```

---

## 🧩 Architectural Recipes & Code Snippets

### 1. The 3-Layer Signature Background Formula

Place this at the very top of your `<body>` to give your entire application the signature DejaQ atmosphere:

```html
<!-- Layer 1: Dark background color applied to body/html (#050a14) -->

<!-- Layer 2: Photographic Starry Sky -->
<div class="bg-sky"></div>

<!-- Layer 3: Stipple Halftone Dot Matrix Overlay -->
<div class="bg-halftone-overlay"></div>

<!-- Foreground Container (z-index: 2 ensures content sits on top) -->
<main class="page-shell">
  <!-- Your content goes here -->
</main>
```

Corresponding CSS:
```css
/* Dark Obsidian Base */
body {
  background-color: #050a14;
  color: #ffffff;
  font-family: 'Plus Jakarta Sans', sans-serif;
  margin: 0;
}

/* Layer 2: Photographic Sky */
.bg-sky {
  position: fixed;
  top: 0; left: 0; width: 100%; height: 100%;
  background: url('assets/hero_bg_full.jpg') center bottom / cover no-repeat;
  opacity: 0.88;
  z-index: 0;
  pointer-events: none;
}

/* Layer 3: Halftone Texture */
.bg-halftone-overlay {
  position: fixed;
  top: 0; left: 0; width: 100%; height: 100%;
  background-image: radial-gradient(circle, rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 10px 10px;
  mix-blend-mode: overlay;
  pointer-events: none;
  z-index: 1;
}

/* Foreground Container */
.page-shell {
  position: relative;
  z-index: 2;
  width: 100%;
}
```

---

### 2. The 3D Glass Showcase Slab

The central hero showcase card tilts in 3D space with specular lighting:

```html
<div class="showcase-3d-slab">
  <!-- Left Side: Interactive Area -->
  <div class="panel-detector">
    <div class="specular-highlight"></div>
    
    <!-- Glass Search Bar -->
    <div class="search-bar">
      <svg class="search-icon" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
      </svg>
      <input type="text" class="search-input" placeholder="Type a prompt or question...">
      <button class="search-submit">&rarr;</button>
    </div>

    <!-- Glass Result Card -->
    <div class="card-item">
      <div class="card-item-header">
        <span class="card-item-label"><span class="icon-plus">+</span> Output Query</span>
        <span class="badge-pill badge-different"><span class="badge-check">&#10003;</span> Unique</span>
      </div>
      <div class="card-item-text">What is the photoelectric effect in physics?</div>
    </div>
  </div>

  <!-- Right Side: Metrics / Distribution Trackers -->
  <div class="panel-coverage">
    <div style="font-size: 12px; font-weight: 700; color: #fff; margin-bottom: 10px;">Metric Track</div>
    <div class="cov-item">
      <span class="cov-name">Accuracy</span>
      <div class="cov-track"><div class="cov-bar" style="width: 75%;"></div></div>
      <span class="cov-val">75%</span>
    </div>
  </div>
</div>
```

---

### 3. The Callout Banner with Floating Star Badge

A retro-futuristic callout with a stark contrast black badge and cream surface:

```html
<div class="callout-wrapper">
  <!-- Black Square Floating Badge -->
  <div class="callout-star-badge">
    <svg viewBox="0 0 24 24">
      <path d="M12 0L14.4 8.6L23 11L14.4 13.4L12 22L9.6 13.4L1 11L9.6 8.6Z" />
    </svg>
  </div>
  
  <!-- Banner Body -->
  <div class="callout-banner">
    <div class="callout-text">
      Explain your product value proposition or announcement here in clean, concise typography.
    </div>
    <a href="#" class="btn btn-dark">
      Get Started &rarr;
    </a>
  </div>
</div>
```

---

### 4. Buttons & Badges

```html
<!-- Cream Primary Button -->
<a href="#" class="btn btn-cream">Get started &rarr;</a>

<!-- Glass Ghost Button with Play Circle -->
<button class="btn btn-glass">Watch demo <span class="play-circle">&#9655;</span></button>

<!-- Badges -->
<span class="badge-pill badge-green"><span class="badge-check">&#10003;</span> Different</span>
<span class="badge-pill badge-amber"><span class="badge-dot"></span> Semantic duplicate</span>
<span class="badge-pill badge-blue"><span class="badge-dot"></span> AI Analyzing</span>
```

---

## ⚛️ Modern Framework Integration (React / Next.js / Tailwind)

### If using Tailwind CSS:

Add the custom design tokens to your `tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        'space-dark': '#050a14',
        'cream': '#f0ece1',
        'cream-hover': '#ffffff',
        'banner-bg': '#d7d0c5',
        'banner-text': '#161c28',
        'glass-card': 'rgba(9, 20, 42, 0.68)',
        'glass-inner': 'rgba(14, 28, 56, 0.65)',
        'glass-border': 'rgba(255, 255, 255, 0.12)',
        'glass-border-bright': 'rgba(255, 255, 255, 0.22)',
      },
      fontFamily: {
        body: ['var(--font-jakarta)', 'sans-serif'],
        mono: ['var(--font-space)', 'monospace'],
      },
    },
  },
  plugins: [],
}
```

### In Next.js (App Router):

Import fonts using `next/font/google` in `app/layout.tsx`:

```tsx
import { Plus_Jakarta_Sans, Space_Grotesk } from 'next/font/google';
import './globals.css';
import '@/ui-kit/ui-style.css'; // Or copy to your styles

const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-jakarta',
});

const space = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space',
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${jakarta.variable} ${space.variable}`}>
      <body className="bg-space-dark text-white relative">
        <div className="bg-sky" />
        <div className="bg-halftone-overlay" />
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
```

---

## 🌟 Tips for Perfect Polish

1. **Avoid Scrolling on Hero Sections**: Keep the landing page fitted inside `100vh` on desktop using flex/grid with `justify-content: space-between` and `overflow: hidden`.
2. **Glass Saturation**: Always combine `backdrop-filter: blur(...)` with `saturate(180%-190%)` so the colors of the starry background remain vivid through the frosted glass.
3. **Specular Edge Lines**: Use a 1px pseudo-element gradient (`linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent)`) across top borders to simulate real optical glass reflection.
4. **Mobile Responsiveness**: On viewports under 980px, disable the 3D rotation (`transform: none !important`) and stack the panels vertically for touch devices.

---

Enjoy building your next project with this design system!

