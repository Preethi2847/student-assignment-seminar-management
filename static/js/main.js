document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('login-form');
  if (form) {
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      const username = document.getElementById('username')?.value?.trim();
      const password = document.getElementById('password')?.value;
      const role = document.getElementById('role')?.value || 'student';
      const messageEl = document.getElementById('form-message');

      if (!username || !password) {
        showMessage(messageEl, 'Please enter both username and password.', 'error');
        return;
      }

      try {
        const response = await fetch(form.action || '/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password, role })
        });

        const data = await response.json();
        if (response.ok) {
          showMessage(messageEl, data.message || 'Login successful', 'success');
          window.location.href = '/';
        } else {
          showMessage(messageEl, data.error || 'Login failed', 'error');
        }
      } catch (error) {
        showMessage(messageEl, 'Something went wrong. Please try again.', 'error');
      }
    });
  }

  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      const full_name = document.getElementById('full_name')?.value?.trim();
      const username = document.getElementById('username')?.value?.trim();
      const email = document.getElementById('email')?.value?.trim();
      const password = document.getElementById('password')?.value;
      const role = document.getElementById('role')?.value || 'student';
      const department = document.getElementById('department')?.value || '';
      const year_of_study = document.getElementById('year_of_study')?.value || '';
      const messageEl = document.getElementById('form-message');

      if (!full_name || !username || !email || !password) {
        showMessage(messageEl, 'Please fill in all required fields.', 'error');
        return;
      }

      try {
        const response = await fetch(registerForm.action || '/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ full_name, username, email, password, role, department, year_of_study })
        });

        const data = await response.json();
        if (response.ok) {
          showMessage(messageEl, data.message || 'Registration successful', 'success');
          setTimeout(() => {
            window.location.href = '/login?role=' + encodeURIComponent(role);
          }, 800);
        } else {
          showMessage(messageEl, data.error || 'Registration failed', 'error');
        }
      } catch (error) {
        showMessage(messageEl, 'Something went wrong. Please try again.', 'error');
      }
    });
  }
});

function showMessage(element, message, type) {
  if (!element) return;
  element.textContent = message;
  element.className = 'alert show ' + type;
}
