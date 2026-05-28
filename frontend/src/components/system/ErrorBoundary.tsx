import React from "react";

type Props = {
  children: React.ReactNode;
  onError?: (error: Error, info: React.ErrorInfo) => void;
  fallback?: (error: Error, reset: () => void) => React.ReactNode;
};

type State = { error: Error | null };

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    this.props.onError?.(error, info);
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  render(): React.ReactNode {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback(this.state.error, this.reset);
      return (
        <div
          role="alert"
          className="m-6 rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 p-6 text-red-800 dark:text-red-200"
        >
          <h2 className="text-lg font-semibold mb-2">面板出错</h2>
          <p className="text-sm opacity-80 mb-4">
            渲染时发生未捕获错误，已为你阻止白屏。可重试或刷新页面。
          </p>
          <pre className="text-xs whitespace-pre-wrap break-words bg-red-100/60 dark:bg-red-900/40 rounded p-3 mb-4 max-h-40 overflow-auto">
            {this.state.error.message}
          </pre>
          <button
            type="button"
            onClick={this.reset}
            className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
