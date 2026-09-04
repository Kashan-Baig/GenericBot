import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = { title: 'Flowcraft — Visual chatbot automation', description: 'Build, test, and activate conversational experiences with Flowcraft.', generator: 'v0.app' }
export const viewport: Viewport = { colorScheme: 'light', themeColor: '#f7f8fb' }
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en" className="bg-background"><body className="antialiased">{children}{process.env.NODE_ENV === 'production' && <Analytics />}</body></html> }
