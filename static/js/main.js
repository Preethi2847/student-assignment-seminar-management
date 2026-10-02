document.addEventListener('DOMContentLoaded', () => {
  // Handle form submissions
  const forms = document.querySelectorAll('form[data-ajax="true"]');
  forms.forEach(form => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      const originalText = button.innerHTML;

      button.disabled = true;
      button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

      try {
        const formData = new FormData(form);
        const response = await fetch(form.action, {
          method: form.method || 'POST',
          body: formData
        });

        if (response.ok) {
          if (form.dataset.redirect) {
            window.location.href = form.dataset.redirect;
          } else {
            window.location.reload();
          }
        } else {
          alert('Something went wrong. Please try again.');
        }
      } catch (error) {
        alert('Request failed.');
      } finally {
        button.disabled = false;
        button.innerHTML = originalText;
      }
    });
  });

  // Tab switching
  const tabButtons = document.querySelectorAll('[data-tab-target]');
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const target = button.getAttribute('data-tab-target');
      document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.toggle('active', el.id === target);
      });
      document.querySelectorAll('[data-tab-target]').forEach(el => {
        el.classList.toggle('active', el === button);
      });
    });
  });

  // Modal handling
  const modals = document.querySelectorAll('[data-toggle="modal"]');
  modals.forEach(modal => {
    modal.addEventListener('click', () => {
      const target = modal.getAttribute('data-target');
      const modalElement = document.querySelector(target);
      if (modalElement) {
        modalElement.style.display = 'flex';
      }
    });
  });

  // Close modals when clicking outside
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
      e.target.style.display = 'none';
    }
  });

  // Close alert messages
  document.querySelectorAll('.alert .close').forEach(btn => {
    btn.addEventListener('click', function() {
      this.parentElement.style.display = 'none';
    });
  });
});

// Utility function for API calls
async function apiCall(endpoint, method = 'GET', data = null) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    }
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(endpoint, options);
  return {
    ok: response.ok,
    status: response.status,
    data: await response.json()
  };
}
