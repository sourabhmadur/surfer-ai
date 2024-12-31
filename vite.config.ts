import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'
import { writeFileSync, mkdirSync, existsSync, copyFileSync } from 'fs'
import sharp from 'sharp'

// Plugin to generate icons
const generateIconsPlugin = () => ({
  name: 'generate-icons',
  closeBundle: async () => {
    console.log('Starting icon generation...')
    
    try {
      // Check if source SVG exists
      const svgPath = resolve(__dirname, 'src/assets/icon.svg')
      if (!existsSync(svgPath)) {
        throw new Error(`Source SVG not found at ${svgPath}`)
      }

      // Generate icon from SVG
      const svgBuffer = await sharp(svgPath)
        .resize(128, 128)
        .png()
        .toBuffer()
      
      // Write the icon file
      const iconPath = resolve(__dirname, 'dist/icon.png')
      writeFileSync(iconPath, svgBuffer)
      
      if (existsSync(iconPath)) {
        console.log(`✓ Icon generated successfully at ${iconPath}`)
      } else {
        console.error('Icon file was not created')
      }
    } catch (error) {
      console.error('Error generating icon:', error)
    }
  }
})

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), generateIconsPlugin()],
  publicDir: 'public',
  build: {
    sourcemap: true,
    minify: false,
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        background: resolve(__dirname, 'src/background/background.ts'),
        content: resolve(__dirname, 'src/content/content.ts'),
        sidepanel: resolve(__dirname, 'sidepanel.html')
      },
      output: {
        format: 'es',
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name].[hash].js',
        assetFileNames: 'assets/[name][extname]'
      }
    }
  }
})
