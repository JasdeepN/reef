  
// Example usage isModalOutOfView after showing the modal:
//   setTimeout(function() {
//     if (isModalOutOfView('#modal-yourTableId')) {
//       console.log('Modal is partially outside the viewport!');
//       // Optionally, adjust modal position here
//     }
//   }, 100); // Delay to allow modal to render

function isModalOutOfView(modalSelector) {
    const modal = document.querySelector(modalSelector);
    if (!modal) return false;
    const rect = modal.getBoundingClientRect();
    const outOfView =
      rect.top < 0 ||
      rect.left < 0 ||
      rect.bottom > (window.innerHeight || document.documentElement.clientHeight) ||
      rect.right > (window.innerWidth || document.documentElement.clientWidth);
    return outOfView;
  }
