VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
	config.vm.define "pymomo" do |pymomo|
	  pymomo.vm.box = "hashicorp/precise64"
	  pymomo.vm.box_url = "https://vagrantcloud.com/hashicorp/precise64/version/2/provider/virtualbox.box"

	  pymomo.vm.provider :virtualbox do |vb|
	    vb.customize ['modifyvm', :id, '--usb', 'on']
	  end

	  pymomo.vm.network "forwarded_port", guest: 80, host: 1111

	  pymomo.vm.provision "shell", inline: "/vagrant/test/install.sh"
	end
end