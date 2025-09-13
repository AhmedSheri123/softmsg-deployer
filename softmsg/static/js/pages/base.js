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

// lazyload سيتم تحميل الصورة الخلفية عند ظهور العنصر 
document.addEventListener('lazybeforeunveil', function(e){
  var bg = e.target.getAttribute('data-bg');
  e.target.style.setProperty('--bg', `url(${bg})`);  // تعيين الصورة على عنصر الـ CSS
});
