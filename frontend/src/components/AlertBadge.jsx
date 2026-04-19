import PropTypes from 'prop-types';

const SEVERITY_CONFIG = {
  critical: { label: 'Critical', className: 'badge-critical' },
  warning: { label: 'Warning', className: 'badge-warning' },
  info: { label: 'Info', className: 'badge-info' },
  success: { label: 'Success', className: 'badge-success' },
};

/**
 * Color-coded severity pill badge.
 */
export default function AlertBadge({ severity }) {
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.info;
  return <span className={config.className}>{config.label}</span>;
}

AlertBadge.propTypes = {
  severity: PropTypes.oneOf(['critical', 'warning', 'info', 'success']).isRequired,
};
