import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const token = request.cookies.get('access_token')
  const isOnboarding = request.nextUrl.pathname.startsWith('/onboarding')
  const isDashboard = request.nextUrl.pathname.startsWith('/dashboard')

  if (!token && (isOnboarding || isDashboard)) {
    const url = request.nextUrl.clone()
    url.pathname = '/auth'
    url.searchParams.set('redirect', request.nextUrl.pathname)
    return NextResponse.redirect(url)
  }

  if (token && request.nextUrl.pathname === '/auth') {
    return NextResponse.redirect(new URL('/onboarding', request.url))
  }
}

export const config = {
  matcher: ['/onboarding/:path*', '/dashboard/:path*', '/auth'],
}
