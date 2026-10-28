using System;
using System.Net;
using System.Windows.Forms;
using Contoso.Billing.Data;

namespace Contoso.Billing.UI
{
    public class CustomerForm : Form
    {
        private readonly CustomerRepository _repository = new CustomerRepository();
        private readonly TextBox _cityTextBox = new TextBox();
        private readonly DataGridView _customerGrid = new DataGridView();

        public CustomerForm()
        {
            var searchButton = new Button { Text = "Search" };
            searchButton.Click += SearchButton_Click;
            var exportButton = new Button { Text = "Export" };
            exportButton.Click += ExportButton_Click;
            Controls.AddRange(new Control[] { _cityTextBox, searchButton, exportButton, _customerGrid });
        }

        private void SearchButton_Click(object sender, EventArgs e)
        {
            _customerGrid.DataSource = _repository.GetCustomersByCity(_cityTextBox.Text);
        }

        private void ExportButton_Click(object sender, EventArgs e)
        {
            using (var client = new WebClient())
            {
                client.UploadString("http://reports.contoso.local/export", _cityTextBox.Text);
            }
            MessageBox.Show("Export completed");
        }
    }
}
