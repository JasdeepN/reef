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



function openModal(data, tableId) {
  console.log("clicked button on table: ", tableId);
  const isEdit = !!data;
  const modalContainer = $(`#modal-container-${tableId}`);
  const modal = $(`#modal-${tableId}`);
  const backdrop = $(`#modalBackdrop-${tableId}`);
  
  modal.find('#modal-title-' + tableId).text(isEdit ? 'Edit Record' : 'Add Record');
  modal.find('input').each(function () {
    const fieldName = $(this).attr('name');
    $(this).val(data ? data[fieldName] || '' : '');
  });

  modalContainer.addClass('show');
  backdrop.addClass('show');
  modal.addClass('show');

  // Ensure modal is centered (in case of dynamic content)
  setTimeout(function() {
    modal.css({
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)'
    });
  }, 50);

  setTimeout(function() {
    if (isModalOutOfView('#modal-' + tableId)) {
      console.log('Modal is partially outside the viewport! Resizing...');
      // Dynamically resize and reposition modal
      //TODO: this needs to be adjusted
      modal.css({
        top: '20%',
        maxHeight: '90vh',
        width: '90vw',
        overflowY: 'auto'
      });
    }
  }, 100);
    // Handle form submission
  $(`#editForm-${tableId}`).off('submit').on('submit', function (e) {
    e.preventDefault();
    const formData = $(this).serializeArray().reduce((obj, item) => {
      obj[item.name] = item.value;
      return obj;
    }, {});
    const url = isEdit ? `/api/v1/edit/${tableId}` : `/api/v1/new/${tableId}`;
    const method = isEdit ? 'PUT' : 'POST';
    if (isEdit) {
      formData.id = data.id; // Include the ID of the row if editing
      console.log("Editing record with ID: ", data.id);
    }
    $.ajax({
      url: url,
      type: method,
      contentType: 'application/json',
      data: JSON.stringify(formData),
        success: function (response) {
        alert(`${isEdit ? 'Record updated' : 'Record added'} successfully.`);
        closeModal(tableId);
        // Reload the DataTable using the table's unique ID
        console.log("Reloading table: ", tableId);

        $(`#${tableId}`).DataTable().ajax.reload(); // Reload the DataTable NOT COMMENTED OUT
      },
      error: function (xhr) {
        alert('Error saving record: ' + xhr.responseText);
      }
    });
  });
      
}


      // Function to close the modal
function closeModal(tableId) {
  $(`#modal-container-${tableId}`).removeClass('show');
  $(`#modalBackdrop-${tableId}`).removeClass('show');
}