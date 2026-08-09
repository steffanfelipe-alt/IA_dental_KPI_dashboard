function ToothbrushIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.3}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-7 w-7"
    >
      <rect x="2" y="9" width="8" height="7" rx="2" />
      <path d="M4.7 9v7M7.3 9v7M2 12.5h8" />
      <path d="M10 11c3-1.6 7-2 10-1.3 1.3.3 2 .9 2 1.8s-.7 1.5-2 1.8c-3 .7-7 .3-10-1.3" />
    </svg>
  );
}

export function LoadingScreen() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="relative flex h-20 w-20 items-center justify-center">
        <div className="absolute inset-0 rounded-full border-2 border-primary-100" />
        <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-primary-500" />
        <div className="text-primary-500">
          <ToothbrushIcon />
        </div>
      </div>

      <p className="text-lg font-semibold text-ink-900">
        <span className="text-primary-600">AI</span> dental dashboard
      </p>
    </main>
  );
}
