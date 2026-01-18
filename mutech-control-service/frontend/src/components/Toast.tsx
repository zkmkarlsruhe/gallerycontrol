interface ToastProps {
  message: string;
  type: 'success' | 'danger' | 'info';
}

export function Toast({ message, type }: ToastProps) {
  return (
    <div className={`toast-notification bg-${type}`}>
      {message}
    </div>
  );
}
