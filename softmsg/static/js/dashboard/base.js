const offcanvasBtn = document.querySelector('.offcanvas-open-close')
const offcanvasBtnIco = document.querySelector('.offcanvas-open-close i')
const offcanvasSidbar = document.querySelector('.offcanvas-sidbar')
const sidbarLinks = document.querySelectorAll('.offcanvas-sidbar .nav-link')
const pathname = window.location.pathname

sidbarLinks.forEach(el => {
    if (pathname == el.pathname) {
        el.classList.add('active')
    }
});


function Hideffcanvas() {
    offcanvasSidbar.classList.remove('show')
    offcanvasSidbar.classList.add('hide')
    offcanvasBtnIco.classList.remove('bi-arrow-bar-left')
    offcanvasBtnIco.classList.add('bi-arrow-bar-right')
}
function offcanvasOpenClose() {
    
    if (offcanvasSidbar.classList.contains('show')) {
        Hideffcanvas()
    } else if (offcanvasSidbar.classList.contains('hide')) {
        offcanvasSidbar.classList.remove('hide')
        offcanvasBtnIco.classList.remove('bi-arrow-bar-right')
        offcanvasBtnIco.classList.add('bi-arrow-bar-left')

    }
}

offcanvasBtn.addEventListener('click', offcanvasOpenClose);
window.onresize = Hideffcanvas;

if (window.screen.width <= 578) {
    Hideffcanvas()
}



  // randomGen
function randomGen() {
    let min = 100000
    let max = 1000000
    return (Math.floor((Math.random())*(max-min+1))+min).toString();
  }
  
  
  
  // Toast Alert
  const toastBox = document.querySelector('#toast-box')
  function showToast(toastID, username, msg, img) {
      if (img == '') {
        img = default_img_profile
      }
    html = `
  
      <!-- Then put toasts within -->
      <div class="toast" role="alert" id="toast${toastID}" aria-live="assertive" aria-atomic="true">
        <div class="toast-header">
          <img src="${img}" class="rounded me-2" alt="..." width="50" style="border-radius: 100% !important;">
          <strong class="me-auto">${username}</strong>
          <small class="text-body-secondary">الان</small>
          <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
          ${msg}
        </div>
      </div>
    `
  
  
    toastBox.insertAdjacentHTML("beforeend", html)
    $(`#toast${toastID}`).toast('show');
  
  };




// Form Bootsrap Validation
(() => {
  'use strict'

  // Fetch all the forms we want to apply custom Bootstrap validation styles to
  const forms = document.querySelectorAll('.needs-validation')

  // Loop over them and prevent submission
  Array.from(forms).forEach(form => {
    form.addEventListener('submit', event => {
      if (!form.checkValidity()) {
        event.preventDefault()
        event.stopPropagation()
      }

      form.classList.add('was-validated')
    }, false)
  })
})()


// Get Request fetch
async function fetchAsync (url) {
  let response = await fetch(url);
  let data = await response.json();
  return data;
  }


// Notifications Messages Popover
$(document).ready(function() {
  var optionsNoti = {
      sanitize: false,
      html: true,
      title: "الاشعارات",
      customClass: 'MessagesPopover',
      //html element
      //content: $("#popover-content")
      content: $('[data-name="popover-content-noti"]').html(),
      //Doing below won't work. Shows title only
      //content: $("#popover-content").html()
      
      fallbackPlacements : ['bottom']
  }
  var exampleElnoti = document.getElementById('noti')
  var popover = new bootstrap.Popover(exampleElnoti, optionsNoti)
})


// read all notifi msgs
function ReadMsgs() {
  fetchAsync(`/accounts/read_all_notifi`).then(data => {
      if (data) {
          if (data.status) {
              document.querySelector('.noti-not-readed-box').classList.add('d-none')                    
          }
      }
      })
}