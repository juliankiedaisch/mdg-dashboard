import './Form.css';

/**
 * Form – Einheitlicher Form-Wrapper
 *
 * @param {function}  onSubmit   – Submit-Handler (preventDefault wird automatisch aufgerufen)
 * @param {React.ReactNode} children – Formular-Inhalte
 * @param {string}    layout     – 'vertical' (default) oder 'horizontal'
 * @param {string}    spacing    – 'sm' | 'md' (default) | 'lg'
 * @param {string}    className  – Zusätzliche CSS-Klassen
 */
function Form({
  onSubmit,
  children,
  layout = 'vertical',
  spacing = 'md',
  className = '',
  ...props
}) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSubmit) onSubmit(e);
  };

  const classNames = [
    'shared-form',
    `shared-form--${layout}`,
    `shared-form--spacing-${spacing}`,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <form className={classNames} onSubmit={handleSubmit} {...props}>
      {children}
    </form>
  );
}

export default Form;
